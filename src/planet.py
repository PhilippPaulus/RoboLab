#!/usr/bin/env python3

# Attention: Do not import the ev3dev.ev3 module in this file
from copy import deepcopy
from enum import IntEnum, unique
from importlib.resources import path
from typing import List, Tuple, Dict, Union


@unique
class Direction(IntEnum):
    """ Directions in shortcut """
    NORTH = 0
    EAST = 90
    SOUTH = 180
    WEST = 270


Weight = int

"""
Weight of a given path (received from the server)

Value:  -1 if blocked path
        >0 for all other paths
        never 0
"""


class Planet():
    
    def __init__(self):
        self.paths = {}
        self.unexplored_directions = {}
        self.explored_nodes = []
        self.unveiled_nodes = []
        self.target: Tuple[int, int] = None

    def add_explored_node(self, coords: Tuple[int, int]):
        if coords not in self.explored_nodes:
            self.explored_nodes.append(coords)
        if coords in self.unveiled_nodes:
            self.unveiled_nodes.remove(coords)

    def add_node_scan(self, coords: Tuple[int, int], directions: Dict[Direction, bool]):
        if coords in self.unexplored_directions.keys():
            return

        possible_directions = [direction for direction in directions.keys() if directions[direction]]

        self.unexplored_directions[coords] = (possible_directions if coords not in self.paths.keys()
            else [direction for direction in possible_directions if direction not in self.paths[coords].keys()])

        print(f"unexplored_dirs: {self.unexplored_directions[coords]}")

    def add_unveiled_node(self, coords: Tuple[int, int]):
        if coords not in self.explored_nodes and coords not in self.unveiled_nodes:
            self.unveiled_nodes.append(coords)    
                
    def should_scan(self, coords: Tuple[int, int]):
        # edge case: all 4 paths already unveiled, no scan needed
        if coords in self.paths.keys():
            if len(self.paths[coords].keys()) == 4:
                return False

        return not coords in self.explored_nodes

    def on_target(self, coords: Tuple[int, int]):
        return self.target == coords

    def exploration_completed(self, coords: Tuple[int, int]):
        # at least one reachable unveiled unexplored node exist
        for unveiled_node in self.unveiled_nodes:
            if self.shortest_path(unveiled_node, coords) is not None:
                return False

        # at least one reachable explored node has one unexplored direction
        for node, unexplored_directions in self.unexplored_directions.items():
            if unexplored_directions:
                if self.shortest_path(node, coords) is not None:
                    return False

        return True

    def add_path(self, start: Tuple[Tuple[int, int], Direction], target: Tuple[Tuple[int, int], Direction], weight: int):
        start_coord, start_direct = start
        target_coord, target_direct = target

        if start_coord not in self.paths.keys():
            self.paths[start_coord] = {}

        self.paths[start_coord][start_direct] = (target_coord, target_direct, weight)
                    
        # adds inverse of path to dict, because of the bidirectionality of paths 

        if target_coord not in self.paths.keys():
            self.paths[target_coord] = {}

        self.paths[target_coord][target_direct] = (start_coord, start_direct, weight)
        
        updated_unveiled_nodes = []

        for unveiled_node in self.unveiled_nodes:
            if unveiled_node not in self.paths.keys():
                updated_unveiled_nodes.append(unveiled_node)
            else:
                if len(self.paths[unveiled_node].keys()) != 4:
                    updated_unveiled_nodes.append(unveiled_node)

        self.unveiled_nodes = updated_unveiled_nodes

    def remove_direct(self, coord: Tuple[int, int], direct: Direction):
        if coord not in self.unexplored_directions.keys():
           return
        if direct in self.unexplored_directions[coord]:
            self.unexplored_directions[coord].remove(direct)

    def remove_unexplored_path(self, start: Tuple[Tuple[int, int], Direction], target: Tuple[Tuple[int, int], Direction]):
        print(f"path explored: start: {start}, target: {target}")

        start_coord, start_direct = start
        self.remove_direct(start_coord, start_direct)

        target_coord, target_direct = target
        self.remove_direct(target_coord, target_direct)   
        
    def get_paths(self) -> Dict[Tuple[int, int], Dict[Direction, Tuple[Tuple[int, int], Direction, Weight]]]:
        return self.paths

    def dijkstra(self, start: Tuple[int, int]) -> Tuple[Dict[Tuple[int, int], int], Dict[Tuple[int, int], Tuple[Tuple[int, int], Direction]]]:
        shortest_path_costs = {}
        best_previous_nodes = {}
        paths: dict = deepcopy(self.paths)

        for coords, val in paths.items():
            shortest_path_costs[coords] = float('inf')
            for direction, (target_coords, target_direction, weight) in val.items():
                if weight == -1:
                    paths[coords][direction] = target_coords, target_direction, float('inf')

        shortest_path_costs[start] = 0
        current_node = start

        while paths:
            if current_node is None:
                current_node = list(paths.keys())[0]
                for coords in paths.keys():
                    if shortest_path_costs[coords] < shortest_path_costs[current_node]:
                        current_node = coords

            for direction, (target_cords, _, weight) in paths[current_node].items():
                current_node_weight = shortest_path_costs[current_node]

                if current_node_weight + weight < shortest_path_costs[target_cords]:
                    shortest_path_costs[target_cords] = current_node_weight + weight
                    best_previous_nodes[target_cords] = current_node, direction

            del paths[current_node]
            current_node = None

        return shortest_path_costs, best_previous_nodes

    def backtrack(self, start: Tuple[int, int], target: Tuple[int, int], best_previous_nodes: Dict[Tuple[int, int], Tuple[Tuple[int, int], Direction]]
        ) -> List[Tuple[Tuple[int, int], Direction]]:

        shortest_path = []
        current_node = target

        while current_node != start:
            best_previous_node, best_direction = best_previous_nodes[current_node]

            for direction, (coords, _, _) in self.paths[best_previous_node].items():
                if coords == current_node and direction == best_direction:
                    shortest_path.append((best_previous_node, direction))
                    current_node = best_previous_node
                    break

        return shortest_path[::-1]

    def shortest_path(self, start: Tuple[int, int], target: Tuple[int, int]) -> Union[None, List[Tuple[Tuple[int, int], Direction]]]:
        if target == start:
            return []

        if target not in self.paths.keys():
            return None

        shortest_path_costs, best_previous_nodes = self.dijkstra(start)

        if shortest_path_costs[target] == float('inf'):
            return None
        
        return self.backtrack(start, target, best_previous_nodes)

    def smartest_direction(self, start: Tuple[int, int]) -> Union[None, Direction]:
        if self.target:
            if start == self.target:
                return None

            shortest_path = self.shortest_path(start, self.target)
            if shortest_path is not None:
                _, direction = shortest_path[0]
                return direction

        #print(self.unexplored_directions)

        # take unexplored direciton on current node
        if start in self.unexplored_directions.keys():
            if self.unexplored_directions[start]:
                print("taking unexplored direction on current node")
                return self.unexplored_directions[start][0]

        # strategy:
        # take direction to shortest path leading to either the nearest unveiled, yet unexplored node
        # or the nearest explored node with unexplored directions

        shortest_path_costs, best_previous_nodes = self.dijkstra(start)

        possible_nodes_costs = {}

        for node, unexplored_directions in self.unexplored_directions.items():
            if unexplored_directions:
                possible_nodes_costs[node] = shortest_path_costs[node]

        for unveiled_node in self.unveiled_nodes:
            possible_nodes_costs[unveiled_node] = shortest_path_costs[unveiled_node]

        if not possible_nodes_costs:
            return None

        if min(possible_nodes_costs.values()) == float('inf'):
            print("no reachable nodes...")
            return None

        target = None
        shortest_path_cost = float('inf')

        for coords, cost in possible_nodes_costs.items():
            if cost < shortest_path_cost:
                shortest_path_cost = cost
                target = coords

        _, direction = self.backtrack(start, target, best_previous_nodes)[0]

        print("taking direction to nearest unexplored node or direction")
        return direction
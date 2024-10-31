#!/usr/bin/env python3

import unittest
from planet import Direction, Planet


class ExampleTestPlanet(unittest.TestCase):
    def setUp(self):
        """
        Instantiates the planet data structure and fills it with paths
        NORTH
        +--+
        |  |
        +-0,3------+
           |       |
          0,2-----2,2 (target)
           |      /
        +-0,1    /
        |  |    /
        +-0,0-1,0
           |
        (start)
        SOUTH

        """
        # Initialize your data structure here
        self.planet = Planet()
        self.planet.add_path(((0, 0), Direction.NORTH), ((0, 1), Direction.SOUTH), 1)
        self.planet.add_path(((0, 1), Direction.WEST), ((0, 0), Direction.WEST), 1)
       

    @unittest.skip('Example test, should not count in final test results')
    def test_target_not_reachable_with_loop(self):
        """
        This test should check that the shortest-path algorithm does not get stuck in a loop between two points while
        searching for a target not reachable nearby

        Result: Target is not reachable
        """
        self.assertIsNone(self.planet.shortest_path((0, 0), (1, 2)))


class TestRoboLabPlanet(unittest.TestCase):
    def setUp(self):

        """
        Instantiates the planet data structure and fills it with paths 
        """
                                    
       # global test paths follow (based on graphic under class setup)

        self.planet = Planet()
        self.planet.add_path(((0, 0), Direction.WEST), ((0, 1), Direction.WEST), 1)
        self.planet.add_path(((0, 0), Direction.NORTH), ((0, 1), Direction.SOUTH), 2)
        self.planet.add_path(((0, 0), Direction.EAST), ((1, 0), Direction.WEST), 3)
        self.planet.add_path(((0, 1), Direction.NORTH), ((0, 2), Direction.SOUTH), 1)
        self.planet.add_path(((0, 3), Direction.WEST), ((0, 3), Direction.NORTH), 1)
        self.planet.add_path(((0, 3), Direction.EAST), ((2, 2), Direction.NORTH), 1)
        self.planet.add_path(((0, 2), Direction.NORTH), ((0, 3), Direction.SOUTH), 1)
        self.planet.add_path(((0, 2), Direction.EAST), ((2, 2), Direction.WEST), 5)
        self.planet.add_path(((1, 0), Direction.NORTH), ((2, 2), Direction.SOUTH), 3)


    def test_integrity(self):
        """
        This test should check that the dictionary returned by "planet.get_paths()" matches the expected structure
        """
        any_planet = Planet() 
        any_planet.add_path(((0, 0), Direction.NORTH), ((0, 1), Direction.SOUTH), 1)
        any_planet.add_path(((0, 1), Direction.NORTH), ((0, 2), Direction.NORTH), 1)

        correct_paths  = {
        
            (0,0): {
                Direction.NORTH: ((0,1), Direction.SOUTH, 1)}, 
            (0,1): {
                Direction.NORTH: ((0,2), Direction.NORTH, 1), 
                Direction.SOUTH: ((0,0), Direction.NORTH, 1)}, 
            (0,2):{
                Direction.NORTH: ((0,1), Direction.NORTH, 1)}
            
         }
    
        
        self.assertEqual(any_planet.get_paths(), correct_paths)


    def test_empty_planet(self):
        """
        This test should check that an empty planet really is empty
        """
        any_planet = Planet()

        if any_planet.get_paths(): 
            self.fail('Planet should be empty, but isnt')

    def test_target(self):
        """
        This test should check that the shortest-path algorithm implemented works.

        Requirement: Minimum distance is three nodes (two paths in list returned)
        """
        correct_shortest_path = [((0,0), Direction.WEST), ((0, 1), Direction.NORTH), ((0,2), Direction.NORTH), ((0, 3), Direction.EAST)]
        self.assertEqual(self.planet.shortest_path((0,0), (2,2)), correct_shortest_path)

    def test_target_not_reachable(self):
        """
        This test should check that a target outside the map or at an unexplored node is not reachable
        """
        
        self.assertEqual(self.planet.shortest_path((0,0), (2,3)), None)

    def test_same_length(self):
        """
        This test should check that the shortest-path algorithm implemented returns a shortest path even if there
        are multiple shortest paths with the same length.

        Requirement: Minimum of two paths with same cost exists, only one is returned by the logic implemented
        """

        any_planet = Planet()

        any_planet.add_path(((0, 0), Direction.WEST), ((0, 1), Direction.WEST), 1)
        any_planet.add_path(((0, 0), Direction.NORTH), ((0, 1), Direction.SOUTH), 2)
        any_planet.add_path(((0, 0), Direction.EAST), ((1, 0), Direction.WEST), 2) #updated weight
        any_planet.add_path(((0, 1), Direction.NORTH), ((0, 2), Direction.SOUTH), 1)
        any_planet.add_path(((0, 3), Direction.WEST), ((0, 3), Direction.NORTH), 1)
        any_planet.add_path(((0, 3), Direction.EAST), ((2, 2), Direction.NORTH), 1)
        any_planet.add_path(((0, 2), Direction.NORTH), ((0, 3), Direction.SOUTH), 1)
        any_planet.add_path(((0, 2), Direction.EAST), ((2, 2), Direction.WEST), 5)
        any_planet.add_path(((1, 0), Direction.NORTH), ((2, 2), Direction.SOUTH), 2) #updated weight
        
        correct_shortest_path1 = [((0,0), Direction.WEST), ((0, 1), Direction.NORTH), ((0,2), Direction.NORTH), ((0, 3), Direction.EAST)]
        correct_shortest_path2 = [((0,0), Direction.EAST), ((1,0), Direction.NORTH)]

        shortest_path = any_planet.shortest_path((0,0), (2,2)) 

        if correct_shortest_path1 == shortest_path or correct_shortest_path2 == shortest_path: 
            return 
        

        self.fail('failed to find one of the correct shortest paths')

    def test_target_with_loop(self):
        """
        This test should check that the shortest-path algorithm does not get stuck in a loop between two points while
        searching for a target nearby

        Result: Target is reachable
        """
        #loop at (0,3)

        correct_shortest_path = [((0,0), Direction.WEST), ((0,1), Direction.NORTH), ((0,2), Direction.NORTH), ((0,3), Direction.EAST)]
        self.assertEqual(self.planet.shortest_path((0,0), (2,2)), correct_shortest_path)

        

    def test_target_not_reachable_with_loop(self):
        """
        This test should check that the shortest-path algorithm does not get stuck in a loop between two points while
        searching for a target not reachable nearby

        Result: Target is not reachable
        """
        #loop at (0,3)

        self.assertIsNone(self.planet.shortest_path((0,0), (3,2)))


    def test_high_weight_circle(self):

        """
        This test ensures that the shortest path algorithm can work with big numbered weights. Based on a circle
        found on Kuehlelement
        """

        any_planet = Planet()

        any_planet.add_path(((1, 1), Direction.NORTH), ((1, 2), Direction.SOUTH), 1)
        any_planet.add_path(((1, 2), Direction.NORTH), ((1, 3), Direction.SOUTH), 10001)
        any_planet.add_path(((1, 2), Direction.EAST), ((1, 3), Direction.EAST), 10002)
        any_planet.add_path(((1, 2), Direction.WEST), ((1, 3), Direction.WEST), 10000)

        correct_path = [((1,3), Direction.WEST), ((1,2), Direction.SOUTH)]


        self.assertEqual(any_planet.shortest_path((1,3), (1,1)), correct_path)


if __name__ == "__main__":
    unittest.main()
    
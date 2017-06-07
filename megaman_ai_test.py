"""Random number generator"""
import random

class MegamanAITest(object):
    """Test Instance for a run in Megaman X"""
    def __init__(self):
        starting_action = random.randint(1, 6)
        self.fitness = 0
        self.actions = [(0, starting_action)] # pos, action

    def get_actions(self):
        """Obtains the set of actions"""
        return self.actions

class MegamanAIRunner(object):
    """Handles creating and running AI tests"""
    def __init__(self, population, destination_position):
        self.current_generation = 1
        self.current_test = 0
        self.tests = self.create_tests(population)
        self.destination_position = destination_position

    @staticmethod
    def create_tests(population):
        """Creates tests based on a required population amount"""
        return [MegamanAITest() for _ in xrange(population)]

    def get_current_test(self):
        """Obtains the currently running test"""
        return self.tests[self.current_test]

    def finish_current_test(self, score):
        """Finishes the current test with a provided fitness score and move to the next one"""
        # Get the current test and assign the fitness score
        test = self.get_current_test()
        test.fitness = score
        # Move so that we are on the next test
        self.current_test = self.current_test + 1
        #print "Incrementing to test #" + str(self.current_test)
        # Check if we are beyond the current list of tests
        if self.current_test >= len(self.tests):
            #print "Generating a new generaetion of tests"
            # If so, create the next generation!
            self.generate_new_generation()
            # Increment the generation
            self.current_generation = self.current_generation + 1
            # And reset the index
            self.current_test = 0

    def is_last_test(self):
        """Checks if this is the last test in the list"""
        return (len(self.tests) - 1) <= self.current_test

    def get_winner(self):
        """Obtains the winner if we have one"""
        for test in self.tests:
            if test.fitness >= self.destination_position:
                return test
        return None

    def have_winner(self):
        """Checks if we have a winning test case"""
        return any(test.fitness >= self.destination_position for test in self.tests)

    def generate_new_generation(self):
        """Generates a new generation of tests"""
        # Check if any test hit the goal. If so, no need for a new generation!
        if self.have_winner():
            return
        # Selection of the best fit - top 20%
        self.tests = sorted(self.tests, key=lambda test: test.fitness, reverse=True)
        self.tests = self.tests[:max(int(0.2 * len(self.tests)), 2)]
        #print "Eliminating until we have " + str(len(self.tests)) + " tests"
        # Crossover
        self.generate_offspring()
        #print "With offspring, we now have " + str(len(self.tests)) + " tests"
        # Mutation
        self.mutate()

    def generate_offspring(self):
        """Generates randomly generated children of provided test cases"""
        offspring = []
        for parent_a in self.tests:
            for parent_b in self.tests:
                if parent_a == parent_b:
                    continue
                new_actions = []
                random_action_split = random.randint(1, self.destination_position)
                a_actions = parent_a.get_actions()
                for pos, action in a_actions:
                    if pos <= random_action_split:
                        new_actions.append((pos, action))
                b_actions = parent_b.get_actions()
                for pos, action in b_actions:
                    if pos > random_action_split:
                        new_actions.append((pos, action))
                child = MegamanAITest()
                child.actions = new_actions
                offspring.append(child)

        self.tests.extend(offspring)

    def mutate(self):
        """Mutates the tests"""
        for test in self.tests:
            for pos in xrange(self.destination_position):
                # 1% chance for mutation
                if random.uniform(0, 1.0) <= 0.01:
                    # Generate the new action
                    new_action = random.randint(1, 6)
                    # Replace the existing action, if possible
                    for idx, (act_pos, act) in enumerate(test.actions):
                        if act_pos == pos:
                            if act != new_action:
                                test.actions[idx] = (act_pos, new_action)
                            return
                    # Otherwise, pop in the new action
                    test.actions.append((pos, new_action))

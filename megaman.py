"""Import Apple Events"""
from Carbon import AppleEvents
from Carbon import AE

import Queue
import struct
import time
import urllib2

from threading import Thread, Lock
from enum import Enum
from pykeyboard import PyKeyboard

from megaman_ai_test import MegamanAIRunner

import Quartz

# http://tasvideos.org/GameResources/SNES/MegaManX/RAMMap.html

def clockms():
    """Returns the amount of time the process has been running in milliseconds"""
    return time.clock() * 1000

def focuswindow(window):
    """Focuses the provided window"""
    if window is None:
        pass
    actevent = AE.AECreateAppleEvent('misc', 'actv', window,
                                     AppleEvents.kAutoGenerateReturnID,
                                     AppleEvents.kAnyTransactionID)
    actevent.AESend(AppleEvents.kAEWaitReply, AppleEvents.kAENormalPriority,
                    AppleEvents.kAEDefaultTimeout)

def findwindow(bundleid):
    """Finds a window identified by the provided bundle identifier"""
    return AE.AECreateDesc(AppleEvents.typeApplicationBundleID, bundleid)

class Action(Enum):
    """Enum of possible actions"""
    MOVE_RIGHT = 1
    MOVE_LEFT = 2
    STOP_MOVEMENT = 3
    JUMP = 4
    SHOOT = 5
    CHARGE = 6
    DASH = 7
    CHANGE_WEAPON = 8
    START = 9

class MegamanAI(object):
    """Class for running the Megaman AI simulation"""

    REST = "http://localhost:1993/"
    LEFT_ARROW = 0x7B
    RIGHT_ARROW = 0x7C
    F4_KEY = 0x76
    DESTINATION_POSITION = 7600
    MIN_POSITION = 10

    def __init__(self):
        # Create initial AI test suite
        self.prev_position = 0
        self.relevant_update_time = time.time()
        self.test_suite = MegamanAIRunner(25, self.DESTINATION_POSITION)
        self.current_ai_actions = list(self.test_suite.get_current_test().actions)
        # Setup state variables
        self.jumping = False
        self.charged_shot = False
        self.playing_game = True
        # Create keyboard
        self.keyboard = PyKeyboard()
        # Focus the game window
        sneswindow = findwindow('org.bsnes.bsnes-plus')
        focuswindow(sneswindow)
        # Sleep briefly to ensure we have the window brought up
        time.sleep(1)
        # Start the game thread
        self.game_thread = Thread(target=self.game_handler)
        self.game_thread.daemon = True
        self.game_thread.start()
        # Start the input thread
        self.input_queue = Queue.Queue()
        self.input_mutex = Lock()
        self.input_thread = Thread(target=self.input_handler)
        self.input_thread.daemon = True
        self.input_thread.start()
        # Start AI handling
        self.update_ai()

    def update_ai(self):
        """Handles AI logic"""

        """print "Do the things"
        self.queue_action(Action.CHARGE)
        time.sleep(3)
        self.queue_action(Action.MOVE_RIGHT)
        time.sleep(1)
        self.queue_action(Action.JUMP)
        time.sleep(3)
        self.queue_action(Action.SHOOT)
        self.queue_action(Action.STOP_MOVEMENT)
        print "Done with the things"
        """
        print "Starting AI simulation"
        print "Generation 1, Test 1"
        while self.playing_game:
            try:
                position = self.x_position()
                #print "At position " + str(position)
                if self.current_ai_actions:
                    for index, (req_pos, action) in enumerate(self.current_ai_actions):
                        if req_pos <= position:
                            action_obj = Action(action)
                            #print "Queueing action " + str(action_obj)
                            self.queue_action(action_obj)
                            del self.current_ai_actions[index]
                            #print str(len(self.current_ai_actions)) + " actions left"
                        else:
                            break
                time.sleep(0.2)
            except KeyboardInterrupt:
                self.exit_handler()

    def queue_action(self, action):
        """Queues an action to be taken"""
        self.input_queue.put(action)

    def input_handler(self):
        """Handles input passed to the game"""
        self.clear_inputs()
        msperframe = 1000 / 30 # 30 fps
        while self.playing_game:
            # current time
            current = clockms()
            # do stuff
            if self.input_queue.qsize() > 0:
                try:
                    action = self.input_queue.get(True, msperframe / 1000)
                    if action:
                        self.perform_action(action)
                    self.input_queue.task_done()
                except Queue.Empty:
                    # empty queue is OK
                    pass
            # get new time
            after = clockms()
            # if we are under the per-frame budget, wait for the rest
            delta = after - current
            sleeptime = msperframe - delta
            if sleeptime > 0:
                time.sleep(sleeptime / 1000) # convert ms back to seconds
            if not self.playing_game:
                break

    def clear_inputs(self):
        """Clears out all of the current inputs that may be set"""
        self.send_unhandled_key(self.LEFT_ARROW, False)
        self.send_unhandled_key(self.RIGHT_ARROW, False)
        self.send_unhandled_key(self.F4_KEY, False)
        self.keyboard.release_key('a')
        self.keyboard.release_key('z')
        self.keyboard.release_key('x')
        self.keyboard.release_key('c')

    def send_unhandled_key(self, key_code, down):
        """Sends an key to the application that is unhandled by PyKeyboard"""
        event = Quartz.CGEventCreateKeyboardEvent(None, key_code, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)

    def perform_action(self, action):
        """Performs an action in the game"""
        self.input_mutex.acquire()
        self.relevant_update_time = time.time()
        try:
            if action == Action.MOVE_RIGHT:
                self.send_unhandled_key(self.LEFT_ARROW, False)
                self.send_unhandled_key(self.RIGHT_ARROW, True)
            elif action == Action.MOVE_LEFT:
                self.send_unhandled_key(self.RIGHT_ARROW, False)
                self.send_unhandled_key(self.LEFT_ARROW, True)
            elif action == Action.STOP_MOVEMENT:
                self.send_unhandled_key(self.LEFT_ARROW, False)
                self.send_unhandled_key(self.RIGHT_ARROW, False)
            elif action == Action.JUMP:
                if not self.jumping:
                    self.keyboard.press_key('z')
                    self.jumping = True
            elif action == Action.SHOOT:
                if self.charged_shot:
                    self.keyboard.release_key('a')
                else:
                    self.keyboard.tap_key('a')
            elif action == Action.CHARGE:
                self.keyboard.press_key('a')
                self.charged_shot = True
            elif action == Action.DASH:
                self.keyboard.tap_key('x')
            elif action == Action.CHANGE_WEAPON:
                self.keyboard.tap_key('c')
            elif action == Action.START:
                self.keyboard.tap_key('return')
            else:
                print "Unknown action requested: " + str(action)
        finally:
            self.input_mutex.release()

    def memory(self, address, count):
        """Gets specified amount of memory starting in an address"""
        url = MegamanAI.REST + "?position=" + address + "&count=" + str(count)
        data = urllib2.urlopen(url).read()[::2]
        if count == 2:
            return struct.unpack('H', data)[0]
        if count == 1:
            return struct.unpack('B', data)[0]

    def x_position(self):
        """Obtains the memory set for 'current X position'"""
        return self.memory("7e0bad", 2)

    def y_position(self):
        """Obtains the memory set for 'current Y position'"""
        return self.memory("7e0bb0", 2)

    def health(self):
        """Obtains the memory set for 'current health'"""
        return self.memory("7e0bcf", 1)

    def level(self):
        """Obtains the memory set for 'current level'"""
        return self.memory("7e1f7a", 1)

    def isjumping(self):
        """Identifies if we are jumping or not"""
        jump_height = self.memory("7e0bc4", 2)
        #print "Found jump height of " + str(jump_height)
        return jump_height > 0

    def is_showing_demo(self):
        """Checks if we are showing a demo on the title screen"""
        return self.memory("7e003b", 1) > 0

    def exit_handler(self):
        """Handles exiting the simulation"""
        print "Exiting AI simulation"
        self.playing_game = False
        self.input_thread.join()
        self.game_thread.join()
        while not self.input_queue.empty():
            self.input_queue.get()
            self.input_queue.task_done()
        self.input_queue.join()
        self.clear_inputs()

    def check_jumping(self):
        """Updates the jumping state if it was previously found to be true"""
        if not self.jumping:
            return
        self.jumping = self.isjumping()
        if self.jumping:
            return
        self.keyboard.release_key('z')

    def game_handler(self):
        """Game-thread for Megaman AI"""
        msperframe = 1000 / 30 # 30 fps
        while self.playing_game:
            # current time
            current = clockms()
            # do stuff
            if self.is_showing_demo():
                self.queue_action(Action.START)
                self.queue_action(Action.START)
                self.queue_action(Action.START)
                self.queue_action(Action.START)
                self.queue_action(Action.START)
            self.check_jumping()
            self.check_death()
            self.check_stalled()
            self.check_min_pos()
            # get new time
            after = clockms()
            # if we are under the per-frame budget, wait for the rest
            delta = after - current
            sleeptime = msperframe - delta
            if sleeptime > 0:
                time.sleep(sleeptime / 1000) # convert ms back to seconds
            if not self.playing_game:
                break

    def check_death(self):
        """Checks if X died. Load the save state!"""
        if self.health() <= 0:
            #print "X died!"
            #print "Score was " + str(self.ai_get_score())
            #print "Restarting"
            self.restart()

    def check_stalled(self):
        """Checks if X is standing still for longer than 10 seconds"""
        cur_pos = self.x_position()
        if cur_pos == self.prev_position:
            seconds_standing_still = time.time() - self.relevant_update_time
            if seconds_standing_still > 10:
                #print "Score was " + str(self.ai_get_score())
                #print "Restarting"
                self.restart()
        else:
            self.prev_position = cur_pos
            self.relevant_update_time = time.time()

    def check_min_pos(self):
        """Ensures X has not retreated back past the minimum position"""
        cur_pos = self.x_position()
        if cur_pos < self.MIN_POSITION:
            #print "Score was " + str(self.ai_get_score())
            #print "Restarting"
            self.restart()

    def ai_get_score(self):
        """Obtains our AI score for how well we are doing"""
        # Distance * health ?
        return self.x_position()

    def next_test(self):
        """Goes to the next AI Test"""
        score = self.ai_get_score()
        print "Restarting | Score was " + str(score)
        self.test_suite.finish_current_test(score)
        self.current_ai_actions = list(self.test_suite.get_current_test().actions)
        gen_num = self.test_suite.current_generation
        test_num = self.test_suite.current_test + 1
        print "Generation " + str(gen_num) + ", Test " + str(test_num)

    def restart(self):
        """Restarts the game from the quicksave"""
        # Move winner check to a better area
        winner = self.test_suite.get_winner()
        if winner is not None:
            print "WINNER: " + winner
            return

        self.send_unhandled_key(self.F4_KEY, True)
        time.sleep(1)
        self.send_unhandled_key(self.F4_KEY, False)
        self.clear_inputs()
        self.relevant_update_time = time.time()
        self.next_test()

if __name__ == "__main__":
    # Create AI system
    MEGAMAN_AI = MegamanAI()

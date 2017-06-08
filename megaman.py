"""Import Apple Events"""
from Carbon import AppleEvents
from Carbon import AE

import Queue
import struct
import time
import urllib2

from threading import Thread, Lock
from pykeyboard import PyKeyboard

from megaman_action import MegamanAction
from megaman_ai_test import MegamanAIRunner

from Tkinter import *

import Quartz

# Memory offsets obtained from:
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

class MegamanAI(object):
    """Class for running the Megaman AI simulation"""

    REST = "http://localhost:1993/"
    BSNES_BUNDLE_ID = "org.bsnes.bsnes-plus"
    LEFT_ARROW = 0x7B
    RIGHT_ARROW = 0x7C
    F4_KEY = 0x76
    DESTINATION_POSITION = 7600
    MIN_POSITION = 100
    INITIAL_TESTS = 25
    SHOW_UI = True

    def __init__(self):
        """Constructor"""
        # Create initial AI test suite
        self.prev_position = 0
        self.relevant_update_time = time.time()
        self.test_suite = MegamanAIRunner(self.INITIAL_TESTS, self.DESTINATION_POSITION)
        self.current_ai_actions = list(self.test_suite.get_current_test().actions)
        # Setup state variables
        self.jumping = False
        self.charged_shot = False
        self.playing_game = True
        # Create keyboard
        self.keyboard = PyKeyboard()
        # Focus the game window
        sneswindow = findwindow(self.BSNES_BUNDLE_ID)
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
        # Show UI windows
        self.has_ui = self.SHOW_UI
        self.best_score_so_far = 0
        self.generation_text = "Generation 1, Test 1"
        self.ui_show()
        # Start AI handling
        self.update_ai()

    def update_ai(self):
        """Handles AI logic"""
        print "Starting AI simulation"
        print "Generation 1, Test 1"
        while self.playing_game:
            try:
                position = self.x_position()
                #print "At position " + str(position)
                if self.current_ai_actions:
                    for index, (req_pos, action) in enumerate(self.current_ai_actions):
                        if req_pos <= position:
                            action_obj = MegamanAction(action)
                            #print "Queueing action " + str(action_obj)
                            self.queue_action(action_obj)
                            del self.current_ai_actions[index]
                            #print str(len(self.current_ai_actions)) + " actions left"
                        else:
                            break
                self.ui_update()
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
                    continue
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
            if action == MegamanAction.MOVE_RIGHT:
                self.send_unhandled_key(self.LEFT_ARROW, False)
                self.send_unhandled_key(self.RIGHT_ARROW, True)
            elif action == MegamanAction.MOVE_LEFT:
                self.send_unhandled_key(self.RIGHT_ARROW, False)
                self.send_unhandled_key(self.LEFT_ARROW, True)
            elif action == MegamanAction.STOP_MOVEMENT:
                self.send_unhandled_key(self.LEFT_ARROW, False)
                self.send_unhandled_key(self.RIGHT_ARROW, False)
            elif action == MegamanAction.JUMP:
                if not self.jumping:
                    self.keyboard.press_key('z')
                    self.jumping = True
            elif action == MegamanAction.SHOOT:
                if self.charged_shot:
                    self.keyboard.release_key('a')
                else:
                    self.keyboard.tap_key('a')
            elif action == MegamanAction.CHARGE:
                self.keyboard.press_key('a')
                self.charged_shot = True
            elif action == MegamanAction.DASH:
                self.keyboard.tap_key('x')
            elif action == MegamanAction.CHANGE_WEAPON:
                self.keyboard.tap_key('c')
            elif action == MegamanAction.START:
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
                self.queue_action(MegamanAction.START)
                self.queue_action(MegamanAction.START)
                self.queue_action(MegamanAction.START)
                self.queue_action(MegamanAction.START)
                self.queue_action(MegamanAction.START)
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
        self.best_score_so_far = max(score, self.best_score_so_far)
        self.test_suite.finish_current_test(score)
        self.current_ai_actions = list(self.test_suite.get_current_test().actions)
        gen_num = self.test_suite.current_generation
        test_num = self.test_suite.current_test + 1
        self.generation_text = "Generation " + str(gen_num) + ", Test " + str(test_num)
        print self.generation_text

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

    def ui_show(self):
        """Shows the UI"""
        self.status_ui = Tk()
        self.status_label = Label(self.status_ui, text="Generation 888 | Test 8888",
                                  bg="black", fg="green", font=(None, 18),
                                  height=1, width=22)
        self.status_label.pack()
        self.best_ui = Tk()
        self.best_label = Label(self.best_ui, text="Best: 999999",
                                bg="black", fg="green", font=(None, 18),
                                height=1, width=22)
        self.best_label.pack()
        #T.insert(END, "Just a text Widget\nin two lines\n")

    def ui_update(self):
        """Updates the UI"""
        if self.has_ui:
            self.status_label.config(text=self.generation_text)
            self.best_label.config(text="Best: " + str(self.best_score_so_far))
            self.status_ui.update_idletasks()
            self.best_ui.update_idletasks()
            self.status_ui.update()
            self.best_ui.update()

if __name__ == "__main__":
    # Create AI system
    MEGAMAN_AI = MegamanAI()

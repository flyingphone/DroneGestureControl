import cv2
import time
import sys
import json
from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
import mediapipe as mp
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
mp_hands = mp.solutions.hands

print("here0")

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///locations.sqlite3'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:justinaubin@localhost/positions.db'
 
# Creating an SQLAlchemy instance
db = SQLAlchemy(app)
db.init_app(app)

db = SQLAlchemy(app)
class HandLocation(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    #    name = db.Column(db.String(100))
    hand_x = db.Column(db.String(50))  
    hand_y = db.Column(db.String(50))
    hand_z = db.Column(db.String(50))

    def __init__(self, hand_x, hand_y, hand_z):
        self.hand_x = hand_x
        self.hand_y = hand_y
        self.hand_z = hand_z

class MovementVector(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    roll = db.Column(db.String(50))  
    pitch = db.Column(db.String(50))
    yaw = db.Column(db.String(50))

    def __init__(self, roll, pitch, yaw):
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw

class HandTracker:

    def __init__(self):
        # self.hand_locations = []
        # For webcam input:
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.startCamera()

    @classmethod
    def inBounds(cls, x_coor, y_coor):
        if x_coor >= 1 or x_coor <= 0:
            return False
        if y_coor >= 1 or y_coor <= 0:
            return False
        
        return True

    @classmethod
    def noMovement(cls, interval_average_x, interval_average_y, hand_width, hand_length):
        '''Return True if hand stationary and in fist (based on hand measurements)'''

        # if interval_average_x and interval_average_x < 15 and interval_average_y and interval_average_y < 15:
        #     print("false alarm")
        if interval_average_x and interval_average_x > 15 or interval_average_y and interval_average_y > 15:
            return False
        if hand_width < 90 or hand_width > 150:
            return False
        if hand_length > 100:
            return False

        print(hand_width, hand_length)

        return True

    @classmethod
    def getAverages(cls, hand_landmarks, image_height, image_width):
        average_x_position = 0
        average_y_position = 0
        average_z_position = 0
        num_landmarks = 0
        # TODO: right now closes if hand doesn 't move at all, but change to 
        # only close if 
        # this and in fist
        for landmark_name in mp_hands.HandLandmark:

            x_coor = hand_landmarks.landmark[landmark_name].x
            y_coor = hand_landmarks.landmark[landmark_name].y
            z_coor = hand_landmarks.landmark[landmark_name].z
            if HandTracker.inBounds(x_coor, y_coor):
                num_landmarks += 1

            average_x_position += x_coor * image_width
            average_y_position += y_coor * image_height
            average_z_position += z_coor * 1000
        
        if num_landmarks:
            average_x_position /= num_landmarks
            average_y_position /= num_landmarks
            average_z_position /= num_landmarks

        return average_x_position, average_y_position, average_z_position

    @classmethod
    def trackMovements(cls, last_ten_lists, positions):
        # print("tracking")

        x_last_ten, y_last_ten, z_last_ten = last_ten_lists
        x, y, z = positions

        x_average_continual = sum(x_last_ten) / 10
        y_average_continual = sum(y_last_ten) / 10
        z_average_continual = sum(z_last_ten) / 10


        roll = 0
        pitch = 0
        yaw = 0
        if z_average_continual > z + 5:
            # print("EAST")
            yaw = 0.3
        elif z_average_continual < z - 5:
            # print("WEST")
            yaw = -0.3
        else:
            yaw = 0
        # TODO: make more accurate by using percentage of hand taking up screen to increase instead of absolute
        # because the closer hand is the easier it is to change
        # average positions
        if y_average_continual > y + 20:
            # print("EAST")
            roll = 0.5
        elif y_average_continual < y - 20:
            # print("WEST")
            roll = -0.5
        else:
            roll = 0

        if x_average_continual > x + 30:
            # print("EAST")
            pitch = 0.5
        elif x_average_continual < x - 30:
            # print("WEST")
            pitch = -0.5
        else:
            pitch = 0

        x_last_ten.pop(0)
        x_last_ten.append(x)
        y_last_ten.pop(0)
        y_last_ten.append(y)
        z_last_ten.pop(0)
        z_last_ten.append(z)
        
        # loc = HandLocation(x_average_continual, y_average_continual, z_average_continual)
        vector = MovementVector(roll, pitch, yaw)
        print(f'vectors: {roll}, {pitch}, {yaw}')
        db.session.add(vector)
        db.session.commit()

    def startCamera(self):
        print("started")

        with mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as hands:
            prev_x_position = 325
            prev_y_position = 250
            prev_z_position = -50
            
            # change to infinity?
            x_low = y_low = z_low = 1000
            x_high = y_high = z_high = -1000
            x_last_ten = [prev_x_position] * 10
            y_last_ten = [prev_y_position] * 10
            z_last_ten = [prev_z_position] * 10
            prev_time = time.time()
            # last_landmark = time.time()
            # num_landmarks = len(mp_hands.HandLandmark)
            while self.cap.isOpened():
                # print("here2")
                # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 700)
                # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 700)
                success, image = self.cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    # If loading a video, use 'break' instead of 'continue'.
                    continue

                # To improve performance, optionally mark the image as not writeable to
                # pass by reference.
                image.flags.writeable = False
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = hands.process(image)

                # Draw the hand annotations on the image.
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                image_height, image_width, _ = image.shape
                if results.multi_hand_landmarks:
                    
                    for hand_landmarks in results.multi_hand_landmarks:
                        average_x_position, average_y_position, average_z_position = HandTracker.getAverages(hand_landmarks, image_height, image_width)

                        # print(f'average x: {average_x_position}, average y: {average_y_position}')
                        # print(f'average z: {average_z_position}')

                        difference_x = average_x_position - prev_x_position
                        difference_y = average_y_position - prev_y_position
                        difference_z = average_z_position - prev_z_position

                        # loc = HandLocation(difference_x, difference_y, difference_z)
                        # loc = HandLocation(average_x_position, average_y_position, average_z_position)
                        # db.session.add(loc)
                        # db.session.commit()

                        # TODO: make close if off screen for too long?
                        time_elasped = time.time() - prev_time
                        # print(time_elasped)
                        if average_x_position > x_high:
                            x_high = average_x_position
                        if average_x_position < x_low:
                            x_low = average_x_position

                        if average_y_position > y_high:
                            y_high = average_y_position
                        if average_y_position < y_low:
                            y_low = average_y_position

                        if average_z_position > z_high:
                            z_high = average_z_position
                        if average_z_position < z_low:
                            z_low = average_z_position
                        
                        # TODO: fix time problem where if you show hand right at end 
                        # of cycle
                        # it closes because the average didn't move
                        # yaw: more positive further away, more negative closer
                        if time_elasped >= 2:
                            
                            # print(x_high,  x_low, y_low, y_high)
                            interval_average_x = x_high - x_low
                            interval_average_y = y_high - y_low
                            interval_average_z = z_high - z_low
                            # print(interval_average_x, interval_average_y)
                            thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].x * image_width
                            pinky_tip = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].x * image_width
                            hand_width = thumb_tip - pinky_tip

                            middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].x * image_height
                            wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x * image_height
                            hand_length = middle_tip - wrist

                            if HandTracker.noMovement(interval_average_x, interval_average_y, hand_width, hand_length):
                                print("yes")
                                # loc = HandLocation(-1000, -1000, -1000)
                                vector = MovementVector(-1000, -1000, -1000)
                                db.session.add(vector)
                                db.session.commit()
                                self.closeCamera()

                            x_high = y_high = z_high = -1000
                            x_low = y_low = z_low = 1000
                            prev_time = time.time()

                        prev_x_position = average_x_position
                        prev_y_position = average_y_position
                        prev_z_position = average_z_position

                        # if difference_x > 200 and difference_y < -150:
                        #     print("NORTHWEST")
                        # elif difference_x > 200 and difference_y > 150:
                        #     print("SOUTHWEST")
                        # elif difference_x > 200: 
                        #     print("WEST")
                        # elif difference_x < -200 and difference_y < -150:
                        #     print("NORTHEAST")
                        # elif difference_x < -200 and difference_y > 150:
                        #     print("SOUTHEAST")
                        # elif difference_x < -200:
                        #     print("EAST")
                        # elif difference_y < -150:
                        #     print("NORTH")
                        # elif difference_y > 150:
                        #     print("SOUTH")
                        # elif difference_z < -150:
                        #     print("FORWARD")
                        # elif difference_z > 20:
                        #     print("BACK")

                        last_ten_lists = (x_last_ten, y_last_ten, z_last_ten)
                        positions = (average_x_position, average_y_position, average_z_position)

                        HandTracker.trackMovements(last_ten_lists, positions)

                        mp_drawing.draw_landmarks(
                            image,
                            hand_landmarks,
                            mp_hands.HAND_CONNECTIONS,
                            mp_drawing_styles.get_default_hand_landmarks_style(),
                            mp_drawing_styles.get_default_hand_connections_style())
                # Flip the image horizontally for a selfie-view display.
                cv2.imshow('MediaPipe Hands', cv2.flip(image, 1))
                if cv2.waitKey(5) & 0xFF == 27:
                    break
        self.cap.release()
        cv2.destroyAllWindows()

    def closeCamera(self):
        print("close")
        self.cap.release()
        cv2.destroyAllWindows()
        # delete all previous locations in db after camera closes
        num_rows_deleted = db.session.query(MovementVector).delete()
        db.session.commit()
        print(num_rows_deleted)
        sys.exit(0)

if __name__ == '__main__':
   db.create_all()
   hand_positions = HandTracker()
#    app.run(debug = True)

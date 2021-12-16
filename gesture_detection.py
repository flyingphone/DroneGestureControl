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
 
# Creating an SQLAlchemy instance
db = SQLAlchemy(app)
db.init_app(app)

db = SQLAlchemy(app)

class MovementVector(db.Model):
    id = db.Column('id', db.Integer, primary_key = True)
    x_vector = db.Column(db.String(50))  
    y_vector = db.Column(db.String(50))
    z_vector = db.Column(db.String(50))
    turn_vector = db.Column(db.String(50))
    timestamp = db.Column(db.String(50))

    def __init__(self, x_vector = 0, y_vector = 0, z_vector = 0, turn_vector = 0, timestamp=-5):
        self.x_vector = x_vector
        self.y_vector = y_vector
        self.z_vector = z_vector
        self.turn_vector = turn_vector
        self.timestamp = timestamp

class HandTracker:

    def __init__(self):
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
    def handTurned(cls, x_vector, y_vector, z_average_continual, z):
        '''Return True if hand direction flipped'''

        if x_vector == y_vector == 0:
            if z_average_continual > 0 and z < 0:
                if abs(z - z_average_continual) > 40:
                    return -1
            elif z_average_continual < 0 and z > 0:
                if abs(z_average_continual - z) > 40:
                    return 1

        return 0

    @classmethod
    def noMovement(cls, interval_average_x, interval_average_y, hand_width, hand_length):
        '''Return True if hand stationary and in fist (based on hand measurements)'''

        # if interval_average_x and interval_average_x < 15 and interval_average_y and interval_average_y < 15:
        #     print("false alarm")
        # print(interval_average_x, interval_average_y, hand_width, hand_length)
        # if interval_average_x and interval_average_x > 15 or interval_average_y and interval_average_y > 15:
        #     return False
        # if hand_width < 90 or hand_width > 150:
        #     return False
        # if hand_length > 100:
        #     return False
        if interval_average_x and interval_average_x > 10 or interval_average_y and interval_average_y > 10:
            return False
        if hand_width < 25 or hand_width > 50:
            return False
        if hand_length > 20:
            return False

        return True

    @classmethod
    def getAverages(cls, hand_landmarks, image_height, image_width):
        average_x_position = 0
        average_y_position = 0
        average_z_position = 0
        num_landmarks = 0

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

        x_last_ten, y_last_ten, z_last_ten = last_ten_lists
        x, y, z = positions

        x_average_continual = sum(x_last_ten) / 10
        y_average_continual = sum(y_last_ten) / 10
        z_average_continual = sum(z_last_ten) / 10

        averages = (x_average_continual, y_average_continual, z_average_continual)

        x_vector = 0
        y_vector = 0
        z_vector = 0
        turn_vector = 0
        # Values flipped because crazyflie documentation states:
        # "positive X is forward positive Y is left positive Z is up"
        if y_average_continual > y + 20:
            x_vector = 0.4
        elif y_average_continual < y - 20:
            x_vector = -0.4
        else:
            x_vector = 0

        if x_average_continual > x + 30:
            y_vector = 0.4
        elif x_average_continual < x - 30:
            y_vector = -0.4
        else:
            y_vector = 0

        turn_vector = HandTracker.handTurned(x_vector, y_vector, z_average_continual, z)
        if turn_vector:
            vector = MovementVector(turn_vector=turn_vector)
            db.session.add(vector)
            db.session.commit()
        else:
            if z_average_continual > z + 5:
                # print("EAST")
                z_vector = 0.2
            elif z_average_continual < z - 5:
                # print("WEST")
                z_vector = -0.2
            else:
                z_vector = 0
        
                timestamp = time.time()
                vector = MovementVector(x_vector, y_vector, z_vector, timestamp=timestamp)
                db.session.add(vector)
                db.session.commit()

        x_last_ten.pop(0)
        x_last_ten.append(x)
        y_last_ten.pop(0)
        y_last_ten.append(y)
        z_last_ten.pop(0)
        z_last_ten.append(z)

    def startCamera(self):
        print("started")

        with mp_hands.Hands(
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as hands:
            prev_x_position = 325
            prev_y_position = 250
            prev_z_position = -50
            
            x_low = y_low = z_low = 1000
            x_high = y_high = z_high = -1000
            x_last_ten = [prev_x_position] * 10
            y_last_ten = [prev_y_position] * 10
            z_last_ten = [prev_z_position] * 10
            prev_time = time.time()

            while self.cap.isOpened():
                success, image = self.cap.read()
                if not success:
                    print("Ignoring empty camera frame.")
                    continue

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


                        difference_x = average_x_position - prev_x_position
                        difference_y = average_y_position - prev_y_position
                        difference_z = average_z_position - prev_z_position

                        time_elasped = time.time() - prev_time
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
                        
                        if time_elasped >= 2:
                            
                            interval_average_x = x_high - x_low
                            interval_average_y = y_high - y_low
                            interval_average_z = z_high - z_low

                            thumb_tip = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP].x * image_width
                            pinky_tip = hand_landmarks.landmark[mp_hands.HandLandmark.PINKY_TIP].x * image_width
                            hand_width = abs(thumb_tip - pinky_tip)

                            middle_tip = hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_TIP].x * image_height
                            wrist = hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x * image_height
                            hand_length = abs(middle_tip - wrist)

                            if HandTracker.noMovement(interval_average_x, interval_average_y, hand_width, hand_length):
                                print("closing")
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

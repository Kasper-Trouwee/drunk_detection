import cv2
import numpy as np
import websockets
import asyncio
import json

ITERATIONS_LOOP = 10

# ARDUINO URL: ws://192.168.4.1:1337
# TEST/PI URL: ws://127.0.0.1:1337
SERVER_URL = "ws://192.168.4.1:1337"


def TakePhoto():
    camera = cv2.VideoCapture(0)

    return_value,image = camera.read()
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    cv2.imwrite('glass.jpg',image)
    camera.release()
    cv2.destroyAllWindows()

def EdgeDetection():
    # Read the original image
    img = cv2.imread('glass.jpg',flags=0)

    y=0
    x=220
    h=600
    w=325
    crop = img[y:y+h, x:x+w]


    # Blur the image for better edge detection
    img_blur = cv2.GaussianBlur(crop,(5,5),0)

    # Canny Edge Detection
    edges = cv2.Canny(image=img_blur, threshold1=30, threshold2=40)
    cv2.imwrite('edges.png',edges)

def CalculateEdges():
    img = cv2.imread("edges.png")
    rows,cols,_ = img.shape

    gray = cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

    corners = cv2.goodFeaturesToTrack(gray,25,0.01,10)
    corners = np.int0(corners)

    # The default values are the center of the image
    # because otherwise the values cant be determined
    pixel_bot_left = [cols/2,rows/2]
    pixel_bot_right = [cols/2,rows/2]
    pixel_top_left = [cols/2,rows/2]
    pixel_top_right = [cols/2,rows/2]

    for i in corners:
        x,y = i.ravel()
        if y <= rows/2 and x < pixel_bot_left[0]:
            pixel_bot_left[0] = x
            pixel_bot_left[1] = y
        elif y <= rows/2 and x > pixel_bot_right[0]:
            pixel_bot_right[0] = x
            pixel_bot_right[1] = y
        elif y >= rows/2 and x < pixel_top_left[0]:
            pixel_top_left[0] = x
            pixel_top_left[1] = y
        elif y >= rows/2 and x > pixel_top_right[0]:
            pixel_top_right[0] = x
            pixel_top_right[1] = y

    #print(str(pixel_bot_left) + "\n" + str(pixel_bot_right))
    #print(str(pixel_top_left) + "\n" + str(pixel_top_right))
    return pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right

def CalculateVolume(pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right):
    # Calculate Pixels
    r1 = abs(pixel_bot_left[0] - pixel_bot_right[0])
    r2 = abs(pixel_top_left[0] - pixel_top_right[0])
    height = (abs(pixel_top_left[1] - pixel_bot_left[1]) + abs(pixel_top_right[1] - pixel_bot_right[1]))/2
    px_avg = (r1 + r2 + height) / 3
    #print("=====PIXELS=====\nR1: " + str(r1) + " px\nR2: " + str(r2) + " px\nH: " + str(height) + " px")

    # Convert pixels to centimeters
    cm_r1 = r1 * 2.54 / 96
    cm_r2 = r2 * 2.54 / 96
    cm_height = height * 2.54 / 96
    cm_avg = (cm_r1 + cm_r2 + cm_height)/3
    #print("=====CENTIMETERS=====\nR1: " + str(cm_r1) + " cm\nR2: " + str(cm_r2) + " cm\nH: " + str(cm_height) + " cm")

    pi = 3.141592653589793

    # Function to calculate Volume
    # of frustum of cone
    def volume( r , R , h ):
        return 1 /3 * pi * h * (r 
                * r + R * R + r * R)

    glass = volume(cm_r1, cm_r2, cm_height)
    glass = glass * 2.54 / 96

    cl = glass
    #print("=====VOLUME=====\nVolume in cl " + str(cl) + "\n")
    return cl

def default_value(value):
    STANDARDIZATION = 0.9
    if value >= 37:
        return 47.5*STANDARDIZATION
    elif value >= 27 and value <= 37:
        return 30*STANDARDIZATION
    elif value <= 27 and value >= 23:
        return 10*STANDARDIZATION
    elif value <= 23 and value >= 15:
        return 10*STANDARDIZATION
    else:
        # Sends Error to the server
        return 0

async def websocket():
    async with websockets.connect(SERVER_URL) as websocket:
        payload = await websocket.recv()
        try:
            start = json.loads(payload)
            detection = start["detect"]
        except:
            pass
        else:
            if detection == True:
                inhoud = main()

                payload = {
                    "device": "raspberry",
                    "inhoud": inhoud
                }

                # Sends the payload to the server
                await websocket.send(json.dumps(payload))

def iterations():
    avg_volume = 0
    for iteration in range(ITERATIONS_LOOP):
        TakePhoto()
        EdgeDetection()
        pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right = CalculateEdges()
        volume = CalculateVolume(pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right)
        while (volume < 2):
                TakePhoto()
                EdgeDetection()
                pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right = CalculateEdges()
                volume = CalculateVolume(pixel_bot_left, pixel_bot_right, pixel_top_left, pixel_top_right)
        print("ITERATION: " + str(iteration + 1))
        avg_volume = avg_volume + volume
    avg_volume = avg_volume/ITERATIONS_LOOP
    avg_volume = avg_volume * 1.5
    print("=====AVG VOLUME=====\n" + str(avg_volume))
    return avg_volume

def main():
    avg_volume_1 = iterations()
    avg_volume_2 = iterations()
    if(abs(avg_volume_1 - avg_volume_2) >= 3):
        print("ERROR probeer opnieuw")
        # Sends error to the server
        return 0
    else:
        volume = (avg_volume_1 + avg_volume_2) /2
        value = default_value(volume)
        # Convert CL to ML
        value = value * 10
        # Sends the corret data to the server
        return value


if __name__ == "__main__":
    while True:
        asyncio.run(websocket())

import cv2
import json
import sys

img = cv2.imread(sys.argv[1])
pts = []

def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        pts.append([x, y])

        cv2.circle(img, (x, y), 5, (0, 0, 255), -1)

        cv2.putText(
            img, str(len(pts)),
            (x + 6, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (0, 0, 255), 2
        )

        cv2.imshow("click", img)

cv2.namedWindow("click", cv2.WINDOW_NORMAL)
cv2.imshow("click", img)

cv2.setMouseCallback("click", on_click)

cv2.waitKey(0)

print(json.dumps(pts))

cv2.destroyAllWindows()
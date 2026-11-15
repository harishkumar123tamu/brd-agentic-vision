"""Local cow bounding-box labeling for BRD hackathon (no Label Studio required).

Run from project root:
    py -3.12 ground_truth/cow_box_labeler.py

Draw boxes around cows by left-clicking and dragging. Press N for next,
P for previous, U to undo, C to clear, Q to save and quit.
YOLO labels go to ground_truth/det_labels; raw frames remain in data_local/frames.
"""
from pathlib import Path
import cv2

FRAMES = Path('data_local/frames')
LABELS = Path('ground_truth/det_labels')
WINDOW = 'COW LABELS | drag box | N next | P previous | U undo | C clear | Q quit'

def read_labels(path, sw, sh):
    boxes = []
    if not path.exists():
        return boxes
    for line in path.read_text(encoding='utf-8').splitlines():
        parts = line.strip().split()
        if len(parts) != 5 or parts[0] != '0':
            continue
        _, cx, cy, ww, hh = map(float, parts)
        x1, y1 = (cx - ww / 2) * sw, (cy - hh / 2) * sh
        x2, y2 = (cx + ww / 2) * sw, (cy + hh / 2) * sh
        boxes.append((int(x1), int(y1), int(x2), int(y2)))
    return boxes

def save_labels(path, boxes, sw, sh):
    lines = []
    for x1, y1, x2, y2 in boxes:
        a, b = sorted((max(0, min(sw-1, x1)), max(0, min(sw-1, x2))))
        c, d = sorted((max(0, min(sh-1, y1)), max(0, min(sh-1, y2))))
        if b - a < 4 or d - c < 4:
            continue
        cx, cy = ((a+b)/2)/sw, ((c+d)/2)/sh
        ww, hh = (b-a)/sw, (d-c)/sh
        lines.append(f'0 {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}')
    path.write_text(('\n'.join(lines) + '\n') if lines else '', encoding='utf-8')
    return len(lines)

def main():
    imgs = sorted([*FRAMES.glob('*.jpg'), *FRAMES.glob('*.jpeg'), *FRAMES.glob('*.png')])
    if not imgs:
        print(f'No images found in {FRAMES.resolve()}')
        return
    LABELS.mkdir(parents=True, exist_ok=True)
    i = 0
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    while 0 <= i < len(imgs):
        src = imgs[i]
        original = cv2.imread(str(src))
        if original is None:
            print('Could not open', src)
            i += 1
            continue
        h, w = original.shape[:2]
        scale = min(1000 / w, 760 / h, 1)
        sw, sh = max(1, int(w*scale)), max(1, int(h*scale))
        base = cv2.resize(original, (sw, sh), interpolation=cv2.INTER_AREA)
        label_file = LABELS / (src.stem + '.txt')
        boxes = read_labels(label_file, sw, sh)
        mouse = {'drag': False, 'start': None, 'end': None}
        def on_mouse(event, x, y, flags, param):
            x, y = max(0, min(x, sw-1)), max(0, min(y, sh-1))
            if event == cv2.EVENT_LBUTTONDOWN:
                mouse['drag'], mouse['start'], mouse['end'] = True, (x,y), (x,y)
            elif event == cv2.EVENT_MOUSEMOVE and mouse['drag']:
                mouse['end'] = (x,y)
            elif event == cv2.EVENT_LBUTTONUP and mouse['drag']:
                mouse['drag'] = False
                sx, sy = mouse['start']
                if abs(x-sx) >= 5 and abs(y-sy) >= 5:
                    boxes.append((sx, sy, x, y))
                mouse['start'] = mouse['end'] = None
        cv2.setMouseCallback(WINDOW, on_mouse)
        while True:
            display = base.copy()
            for j, (x1, y1, x2, y2) in enumerate(boxes, 1):
                cv2.rectangle(display, (x1,y1), (x2,y2), (0,255,0), 2)
                cv2.putText(display, str(j), (min(x1,x2), min(y1,y2)+16), cv2.FONT_HERSHEY_SIMPLEX, .6, (0,255,0), 2)
            if mouse['drag'] and mouse['start'] and mouse['end']:
                cv2.rectangle(display, mouse['start'], mouse['end'], (0,220,255), 2)
            cv2.rectangle(display, (0,0), (sw,52), (0,0,0), -1)
            cv2.putText(display, f'{i+1}/{len(imgs)}  {src.name[:48]}', (8,19), cv2.FONT_HERSHEY_SIMPLEX, .48, (255,255,255), 1)
            cv2.putText(display, f'{len(boxes)} cow boxes | drag | N next | P back | U undo | C clear | Q save/quit', (8,43), cv2.FONT_HERSHEY_SIMPLEX, .47, (255,255,255), 1)
            cv2.imshow(WINDOW, display)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('u'):
                if boxes: boxes.pop()
            elif key == ord('c'):
                boxes.clear()
            elif key in (ord('n'), ord('p'), ord('q'), 27):
                count = save_labels(label_file, boxes, sw, sh)
                print(f'Saved {i+1}/{len(imgs)}: {src.name} = {count} cows')
                if key in (ord('q'), 27):
                    cv2.destroyAllWindows()
                    return
                i += 1 if key == ord('n') else -1
                i = max(0, i)
                break
    cv2.destroyAllWindows()
    print('Finished. Labels stored in:', LABELS.resolve())

if __name__ == '__main__':
    main()

import os
import json
import shutil
import glob
from pathlib import Path

# Source directory
DATA_ROOT = "/Users/Dylan.Min/Documents/Code/work/huodian/data&model/1120data"
# Target directory
TARGET_DIR = "/Users/Dylan.Min/Documents/Code/work/huodian/AIVision/e2e"

def find_defect_images(limit=5):
    count = 0
    # Recursive search for json files
    for json_file in glob.glob(os.path.join(DATA_ROOT, "**/*.json"), recursive=True):
        if count >= limit:
            break
            
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            has_defect = False
            for shape in data.get('shapes', []):
                label = shape.get('label', '').lower()
                # Exclude non-defect labels
                if label not in ['weld', 'hanfeng', 'roi', 'text']:
                    has_defect = True
                    print(f"Found defect: {label} in {json_file}")
                    break
            
            if has_defect:
                # Find corresponding image
                image_path_in_json = data.get('imagePath', '')
                image_path_in_json = image_path_in_json.replace('\\', '/')
                json_dir = os.path.dirname(json_file)
                
                # Try to resolve image path
                img_path = os.path.abspath(os.path.join(json_dir, image_path_in_json))
                
                if not os.path.exists(img_path):
                    # Fallback: try same filename with .bmp in same dir
                    basename = os.path.splitext(os.path.basename(json_file))[0]
                    img_path = os.path.join(json_dir, basename + ".bmp")
                
                if os.path.exists(img_path):
                    count += 1
                    target_name = f"defect_img_{count}.bmp"
                    target_path = os.path.join(TARGET_DIR, target_name)
                    shutil.copy(img_path, target_path)
                    print(f"Copied {img_path} -> {target_path}")
                else:
                    print(f"Image not found for {json_file}")
                    
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

if __name__ == "__main__":
    find_defect_images()


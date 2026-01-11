import requests
import json
import uuid
import os

BASE_URL = "http://localhost:9541/api/v1"
USER_ID = "admin-001"

def print_response(response, title):
    print(f"\n{title} Response: {response.text[:200]}..." if len(response.text) > 200 else f"\n{title} Response: {response.text}")
    if response.status_code not in [200, 201]:
        print(f"FAILED with status code {response.status_code}")
        return None
    try:
        return response.json()
    except:
        return None

def test_file_management():
    # 1. Create Project
    project_name = f"File_Test_Project_{uuid.uuid4().hex[:8]}"
    create_payload = {"ProjectName": project_name, "Description": "File testing"}
    headers = {"user-id": USER_ID, "Content-Type": "application/json"}
    
    print(f"Creating project: {project_name}")
    resp = requests.post(f"{BASE_URL}/projects/create", json=create_payload, headers=headers)
    create_data = print_response(resp, "Create Project")
    if not create_data: return
    project_id = create_data["Data"]["ProjectId"]
    print(f"Created Project ID: {project_id}")

    # 2. Create Directory
    dir_name = "test-images"
    dir_payload = {"Name": dir_name, "ParentDirectoryId": None}
    dir_headers = {"user-id": USER_ID, "project-id": project_id, "Content-Type": "application/json"}
    
    print(f"Creating directory: {dir_name}")
    resp = requests.post(f"{BASE_URL}/directories/create", json=dir_payload, headers=dir_headers)
    dir_data = print_response(resp, "Create Directory")
    if not dir_data: return
    dir_id = dir_data["Data"]["DirId"]
    print(f"Created Directory ID: {dir_id}")

    # 3. Upload File
    print("Uploading file...")
    # Use real image if available, else create dummy
    img_name = "qwe.png"
    created_dummy = False
    
    if not os.path.exists(img_name):
        print(f"Warning: {img_name} not found, creating dummy file.")
        with open(img_name, "wb") as f:
            f.write(os.urandom(1024))
        created_dummy = True

    upload_headers = {
        "user-id": USER_ID,
        "project-id": project_id,
        "directory-id": dir_id
    }
    
    files = {'File': (img_name, open(img_name, 'rb'), 'image/png')}
    resp = requests.post(f"{BASE_URL}/files/upload", files=files, headers=upload_headers)
    upload_data = print_response(resp, "Upload File")
    
    # Close file before potentially deleting
    files['File'][1].close()
    
    # Clean up only if we created a dummy file
    if created_dummy:
        os.remove(img_name)
    
    if not upload_data or upload_data["Data"]["SuccessCount"] == 0:
        print("File upload failed")
        return
    
    file_id = upload_data["Data"]["SuccessFiles"][0]["FileId"]
    print(f"Uploaded File ID: {file_id}")

    # 4. List Files
    print("Listing files...")
    list_params = {
        "projectId": project_id,
        "directoryId": dir_id,
        "page": 0,
        "size": 10
    }
    resp = requests.get(f"{BASE_URL}/files/list", params=list_params, headers=headers)
    list_data = print_response(resp, "List Files")
    
    found = False
    if list_data and list_data["Data"]["content"]:
        for f in list_data["Data"]["content"]:
            if f["fileId"] == file_id:
                print(f"Found uploaded file: {f['originalName']}")
                found = True
                break
    if not found:
        print("ERROR: Uploaded file not found in list")

    # 5. Preview File
    print(f"Previewing file {file_id}...")
    preview_params = {
        "FileId": file_id,
        "ProjectId": project_id,
        "UserId": USER_ID
    }
    resp = requests.get(f"{BASE_URL}/files/preview", params=preview_params)
    if resp.status_code == 200:
        print(f"Preview success: Content-Type={resp.headers.get('Content-Type')}, Size={len(resp.content)} bytes")
    else:
        print(f"Preview failed: {resp.status_code}")

    # 6. Delete File
    print(f"Deleting file {file_id}...")
    del_headers = {
        "user-id": USER_ID,
        "project-id": project_id
    }
    resp = requests.delete(f"{BASE_URL}/files/{file_id}", headers=del_headers)
    print_response(resp, "Delete File")

    # 7. Delete Directory
    print(f"Deleting directory {dir_id}...")
    resp = requests.delete(f"{BASE_URL}/directories/{dir_id}", headers=del_headers)
    print_response(resp, "Delete Directory")

    # 8. Clean up Project
    print(f"Deleting project {project_id}...")
    resp = requests.delete(f"{BASE_URL}/projects/{project_id}", headers=headers)
    print_response(resp, "Delete Project")

    print("\nAll File Management tests passed!")

if __name__ == "__main__":
    try:
        test_file_management()
    except Exception as e:
        print(f"An error occurred: {e}")


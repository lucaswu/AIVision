import requests
import json
import uuid
import sys

BASE_URL = "http://localhost:9541/api/v1/projects"
USER_ID = "admin-001"  # 使用已知的 Admin 用户 ID

def print_response(response, title):
    print(f"\n{title} Response: {response.text}")
    if response.status_code not in [200, 201]:
        print(f"FAILED with status code {response.status_code}")
        return None
    return response.json()

def test_project_lifecycle():
    # 1. Create Project
    project_name = f"Test_Project_{uuid.uuid4().hex[:8]}"
    create_payload = {
        "ProjectName": project_name,
        "Description": "Initial description"
    }
    headers = {
        "user-id": USER_ID,
        "Content-Type": "application/json"
    }
    
    print(f"Creating project: {project_name}")
    resp = requests.post(f"{BASE_URL}/create", json=create_payload, headers=headers)
    create_data = print_response(resp, "Create Project")
    assert create_data is not None
    assert create_data.get("Code") == 200

    project_id = create_data["Data"]["ProjectId"]
    print(f"Created Project ID: {project_id}")

    # 2. List Projects
    print("Listing projects...")
    resp = requests.get(f"{BASE_URL}/list", headers=headers)
    list_data = print_response(resp, "List Projects")
    
    found = False
    if list_data and list_data.get("Data"):
        for proj in list_data["Data"]:
            if proj["Id"] == project_id:
                print(f"Found project in list: {proj['Name']}, FileCount: {proj.get('FileCount')}")
                found = True
                break
    
    if not found:
        print("ERROR: Created project not found in list")
    assert found, "Created project not found in list"

    # 3. Update Project
    update_payload = {
        "ProjectName": project_name + "_Updated",
        "Description": "Updated description"
    }
    print(f"Updating project {project_id}...")
    resp = requests.put(f"{BASE_URL}/{project_id}", json=update_payload, headers=headers)
    update_data = print_response(resp, "Update Project")
    assert update_data is not None
    assert update_data.get("Code") == 200

    # Verify update
    resp = requests.get(f"{BASE_URL}/list", headers=headers)
    list_data = resp.json()
    update_verified = False
    for proj in list_data["Data"]:
        if proj["Id"] == project_id:
            if proj["Name"] == update_payload["ProjectName"] and proj["Description"] == update_payload["Description"]:
                print("Update verified successfully")
                update_verified = True
            else:
                print(f"ERROR: Update verification failed. Got {proj['Name']}, {proj['Description']}")
            break
    assert update_verified, "Project update was not reflected in project list"

    # 4. Delete Project
    print(f"Deleting project {project_id}...")
    resp = requests.delete(f"{BASE_URL}/{project_id}", headers=headers)
    delete_data = print_response(resp, "Delete Project")
    assert delete_data is not None
    assert delete_data.get("Code") == 200

    # Verify deletion
    resp = requests.get(f"{BASE_URL}/list", headers=headers)
    list_data = resp.json()
    found_after_delete = False
    if list_data and list_data.get("Data"):
        for proj in list_data["Data"]:
            if proj["Id"] == project_id:
                found_after_delete = True
                break
    
    if found_after_delete:
        print("ERROR: Project still exists after deletion")
    else:
        print("Deletion verified successfully")
        print("\nAll Project API tests passed!")
    assert not found_after_delete, "Project still exists after deletion"

if __name__ == "__main__":
    try:
        test_project_lifecycle()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

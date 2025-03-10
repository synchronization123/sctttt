import requests

# Configuration
JIRA_URL = "https://jira.demo.almworks.com"
JIRA_TOKEN = "abc"
DOJO_URL = "https://demo.defectdojo.org"
DOJO_TOKEN = "abc"

HEADERS_JIRA = {
    "Authorization": f"Bearer {JIRA_TOKEN}",
    "Accept": "application/json"
}

HEADERS_DOJO = {
    "Authorization": f"Token {DOJO_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def get_dojo_tests():
    """Fetch tests from DefectDojo that have label 'crm_jira' and don't have 'commentfetched' tag."""
    print("\nFetching tests from DefectDojo...")
    response = requests.get(f"{DOJO_URL}/api/v2/tests/", headers=HEADERS_DOJO)
    
    if response.status_code == 200:
        tests = response.json().get("results", [])
        filtered_tests = [
            t for t in tests
            if "crm_jira" in t.get("tags", []) and "commentfetched" not in t.get("tags", [])
        ]
        print(f"✅ Found {len(filtered_tests)} tests that match criteria.")
        return filtered_tests
    else:
        print(f"❌ Failed to fetch tests. Status Code: {response.status_code}")
        return []

def get_dojo_user_info(user_id):
    """Fetch username from DefectDojo users API using user ID."""
    print(f"🔍 Fetching DefectDojo user info for ID: {user_id}...")
    response = requests.get(f"{DOJO_URL}/api/v2/users/{user_id}/", headers=HEADERS_DOJO)

    if response.status_code == 200:
        username = response.json().get("username", "").split("@")[0]  # Remove domain if present
        print(f"✅ Dojo User: {username}")
        return username
    else:
        print(f"❌ Failed to fetch user info for {user_id}. Status Code: {response.status_code}")
        return None

def get_jira_comments(issue_key):
    """Fetch comments for a Jira issue."""
    print(f"\nFetching comments for Jira issue: {issue_key}...")
    response = requests.get(f"{JIRA_URL}/rest/api/2/issue/{issue_key}/comment", headers=HEADERS_JIRA)
    
    if response.status_code == 200:
        comments = response.json().get("comments", [])
        print(f"✅ Found {len(comments)} comments for issue {issue_key}.")
        return comments
    else:
        print(f"❌ Failed to fetch comments for {issue_key}. Status Code: {response.status_code}")
        return []

def update_dojo_test(test_id, new_description):
    """Update test description and add 'commentfetched' tag."""
    print(f"🔄 Updating test ID {test_id} with new description and tag 'commentfetched'...")
    
    update_data = {"description": new_description, "tags": ["crm_jira", "commentfetched"]}
    response = requests.patch(f"{DOJO_URL}/api/v2/tests/{test_id}/", headers=HEADERS_DOJO, json=update_data)
    
    if response.status_code == 200:
        print(f"✅ Successfully updated test {test_id}!")
        return True
    else:
        print(f"❌ Failed to update test {test_id}. Status Code: {response.status_code}")
        return False

def main():
    print("🚀 Starting execution...\n")
    
    tests = get_dojo_tests()  # Fetch relevant tests
    if not tests:
        print("No tests to process. Exiting.")
        return

    for test in tests:
        test_id = test["id"]
        jira_key = test["title"]
        version = test["version"]
        branch_tag = test["branch_tag"]
        lead_id = test["lead"]

        print("\n------------------------------------")
        print(f"🔍 Processing Test ID: {test_id}")
        print(f"🔹 Jira Issue: {jira_key}")
        print(f"🔹 Version: {version}")
        print(f"🔹 Branch Tag: {branch_tag}")
        print(f"🔹 Lead ID: {lead_id}")

        # Validate test scope (must be Completed or Rejected)
        if branch_tag not in ["Completed", "Rejected"]:
            print(f"❌ Skipping test {test_id} (Branch Tag '{branch_tag}' not in scope)")
            continue

        # Get the assigned DefectDojo username
        dojo_username = get_dojo_user_info(lead_id)
        if not dojo_username:
            print(f"⚠️ No valid Dojo username found for lead ID {lead_id}, skipping test {test_id}.")
            continue

        # Get Jira comments
        comments = get_jira_comments(jira_key)

        # Filter comments by author and version text (case insensitive)
        matching_comments = [
            c["body"] for c in comments
            if c["author"]["name"] == dojo_username and version.lower() in c["body"].lower()
        ]

        if matching_comments:
            latest_comment = matching_comments[-1]  # Take the most recent comment
            print(f"✅ Found matching comment: {latest_comment}")
            update_success = update_dojo_test(test_id, latest_comment)

            if update_success:
                print(f"✅ Test {test_id} updated successfully!")
            else:
                print(f"❌ Failed to update test {test_id}.")
        else:
            print(f"⚠️ No matching comment found for test {test_id}, skipping update.")

    print("\n✅ Execution completed.")

if __name__ == "__main__":
    main()

import requests
import json
import re

# DefectDojo API details
DEFECTDOJO_BASE_URL = "https://demo.defectdojo.org/api/v2"
DEFECTDOJO_TOKEN = "abc"

# JIRA API details
JIRA_URL = "https://jira.demo.almworks.com/rest/api/2/search"
JIRA_TOKEN = "abc"

# Common headers
DEFECTDOJO_HEADERS = {
    "Authorization": f"Token {DEFECTDOJO_TOKEN}",
    "Content-Type": "application/json"
}

JIRA_HEADERS = {
    "Authorization": f"Bearer {JIRA_TOKEN}",
    "Content-Type": "application/json"
}

def normalize_version(version):
    """Ensure rX.Y.Z and vX.Y.Z are treated as the same by replacing 'r' with 'v'."""
    return re.sub(r"^[rR]", "v", version, flags=re.IGNORECASE)

def fetch_engagements():
    """Fetch engagements tagged 'crm' and skip those with the label 'crmjiraadded'."""
    print("\n📌 Fetching engagements from DefectDojo...")
    url = f"{DEFECTDOJO_BASE_URL}/engagements/?tags=crm"
    try:
        response = requests.get(url, headers=DEFECTDOJO_HEADERS)
        response.raise_for_status()
        engagements = response.json().get("results", [])
        print(f"✅ Found {len(engagements)} engagements before filtering.")

        # Filter out engagements with the 'crmjiraadded' label
        filtered_engagements = [e for e in engagements if 'crmjiraadded' not in e.get("tags", [])]
        print(f"✅ {len(filtered_engagements)} engagements remain after filtering 'crmjiraadded'.")
        return filtered_engagements

    except requests.RequestException as e:
        print(f"❌ Error fetching engagements: {e}")
        return []

def fetch_jira_issues(version):
    """Fetch JIRA issues where 'Build(s)' matches the given version."""
    normalized_version = normalize_version(version)

    # JQL query to fetch issues with a matching 'Build(s)' field
    jql_query = f'"Build(s)" = "{normalized_version}"'

    print(f"\n📌 Fetching JIRA issues with JQL: {jql_query}")
    start_at = 0
    max_results = 50
    all_issues = []

    while True:
        params = {
            "jql": jql_query,
            "fields": "key,status,issuetype,Build(s)",
            "maxResults": max_results,
            "startAt": start_at
        }
        try:
            response = requests.get(JIRA_URL, headers=JIRA_HEADERS, params=params)
            response.raise_for_status()
            data = response.json()
            
            issues = data.get("issues", [])
            all_issues.extend(issues)

            print(f"✅ Retrieved {len(issues)} issues from JIRA.")

            if len(issues) < max_results:
                break

            start_at += max_results

        except requests.RequestException as e:
            print(f"❌ Error fetching JIRA issues: {e}")
            break

    print(f"📌 Total JIRA issues found: {len(all_issues)}\n")
    return all_issues

def check_existing_tests(engagement_id):
    """Check existing tests under an engagement to avoid duplicates."""
    print(f"📌 Checking existing tests for engagement {engagement_id}...")
    url = f"{DEFECTDOJO_BASE_URL}/tests/?engagement={engagement_id}"
    try:
        response = requests.get(url, headers=DEFECTDOJO_HEADERS)
        response.raise_for_status()
        existing_tests = {test["title"] for test in response.json().get("results", [])}
        print(f"✅ Found {len(existing_tests)} existing tests.")
        return existing_tests
    except requests.RequestException as e:
        print(f"❌ Error checking existing tests: {e}")
        return set()

def create_test(engagement_id, issue, target_start, target_end, lead, version):
    """Create a test under the specified engagement ID for a JIRA issue."""
    status = issue["fields"]["status"]["name"] if "status" in issue["fields"] else "N/A"
    issue_type = issue["fields"]["issuetype"]["name"] if "issuetype" in issue["fields"] else "N/A"

    test_data = {
        "tags": ["crm_jira"],
        "test_type_name": "crm_jira",
        "scan_type": "crm_jira",
        "title": issue["key"], 
        "target_start": target_start,
        "target_end": target_end,
        "engagement": engagement_id,
        "lead": lead,
        "test_type": 150,
        "environment": 6,
        "build_id": status,  
        "commit_hash": issue_type,  # Store the issue type
        "version": version  
    }
    
    print(f"📌 Creating test for issue {issue['key']} under engagement {engagement_id}...")
    url = f"{DEFECTDOJO_BASE_URL}/tests/"
    try:
        response = requests.post(url, headers=DEFECTDOJO_HEADERS, json=test_data)
        response.raise_for_status()
        print(f"✅ Test created for issue {issue['key']} (Version: {version})")
    except requests.RequestException as e:
        print(f"❌ Error creating test for {issue['key']}: {e}")

def update_engagement_with_label(engagement_id):
    """Update the engagement by adding the 'crmjiraadded' label."""
    print(f"📌 Updating engagement {engagement_id} with 'crmjiraadded' label...")
    url = f"{DEFECTDOJO_BASE_URL}/engagements/{engagement_id}/"
    try:
        response = requests.get(url, headers=DEFECTDOJO_HEADERS)
        response.raise_for_status()
        engagement_data = response.json()

        # Add 'crmjiraadded' to existing tags
        new_tags = set(engagement_data.get("tags", []))
        new_tags.add("crmjiraadded")

        update_data = {"tags": list(new_tags)}

        response = requests.patch(url, headers=DEFECTDOJO_HEADERS, json=update_data)
        response.raise_for_status()
        print(f"✅ Engagement {engagement_id} updated successfully.")

    except requests.RequestException as e:
        print(f"❌ Error updating engagement {engagement_id}: {e}")

def main():
    engagements = fetch_engagements()

    if not engagements:
        print("❌ No engagements found. Exiting.")
        return

    for engagement in engagements:
        engagement_id = engagement["id"]
        label = engagement["name"]
        target_start = engagement["target_start"]
        target_end = engagement["target_end"]
        lead = engagement["lead"]
        normalized_version = normalize_version(label)

        print(f"\n🔍 Checking engagement {engagement_id} (Label: {label}, Normalized: {normalized_version})")

        issues = fetch_jira_issues(normalized_version)
        if not issues:
            print(f"❌ No JIRA issues found for version: {normalized_version}")
            continue

        existing_tests = check_existing_tests(engagement_id)

        for issue in issues:
            print(f"📌 Processing JIRA issue {issue['key']}...")

            if issue["key"] not in existing_tests:
                create_test(engagement_id, issue, target_start, target_end, lead, normalized_version)
            else:
                print(f"⚠️ Test already exists for issue {issue['key']} under engagement {engagement_id}")

        # Update engagement with 'crmjiraadded' label
        update_engagement_with_label(engagement_id)

if __name__ == "__main__":
    main()
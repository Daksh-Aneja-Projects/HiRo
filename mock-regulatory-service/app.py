import json
import os
from flask import Flask, jsonify, request

# The directory where the Dockerfile will place the mock data files
MOCK_DATA_DIR = "/app/data"
app = Flask(__name__)

# --- Mock Data Loading ---
def load_all_mock_data():
    """Loads all jurisdictional mock data and combines it into a single list."""
    # CRITICAL FIX: Include the new mock data files (EU, APAC) here
    jurisdictions = ['DE', 'US-CA', 'EU', 'APAC'] # List all mock files created in Dockerfile
    
    all_data = []
    
    for code in jurisdictions:
        file_path = os.path.join(MOCK_DATA_DIR, code)
        try:
            # FIX: Explicitly set encoding to 'utf-8' for robust JSON loading
            with open(file_path, 'r', encoding='utf-8') as f: 
                # Extend the list with the content of each file
                all_data.extend(json.load(f))
        except Exception as e:
            print(f"Warning: Could not load mock data for {code}: {e}")
            
    return all_data

@app.route('/feed', methods=['GET'])
def get_regulatory_feed():
    """
    Serves the combined mock regulatory feed data.
    This endpoint satisfies the backend's DynamicComplianceEngine fetch.
    """
    
    print(f"--- Received request for: {request.path}")
    
    try:
        data = load_all_mock_data()
        
        # NOTE: Ensure the keys match the RegulatoryChange dataclass expectation in dynamic_compliance_engine.py
        # We need to map the mock keys (text, jurisdiction_code, etc.) to the expected keys (description, jurisdiction, etc.)
        mapped_data = [{
            "id": f"MOCK-{i+1}-{item['jurisdiction_code']}",
            "jurisdiction": item['jurisdiction_code'],
            "domain": item['policy_type'] if 'policy_type' in item else 'LABOR_LAW',
            "description": item['text'],
            "effective_date": item['date'],
            "suggested_impact": 'MEDIUM',
            "applied": False
        } for i, item in enumerate(data)]

        print(f"--- Successfully loaded and returning {len(mapped_data)} regulatory changes.")
        return jsonify(mapped_data)
        
    except Exception as e:
        print(f"--- Error: An unexpected error occurred during feed processing: {str(e)}")
        return jsonify({"message": f"An unexpected server error occurred: {str(e)}"}), 500

@app.route('/feed/<jurisdiction_code>', methods=['GET'])
def get_single_regulatory_feed(jurisdiction_code):
    """
    Maintains support for legacy single-jurisdiction lookups (if needed).
    """
    # Simply load all data and filter it for the single jurisdiction
    all_data = load_all_mock_data()
    code = jurisdiction_code.upper()
    
    filtered_data = [item for item in all_data if item.get('jurisdiction_code') == code]
    
    if filtered_data:
        # CRITICAL FIX: Wrap the filtered list in a dictionary with the 'updates' key,
        # which is expected by the fetch_regulatory_updates method in external_api_connector.py.
        # Although the app.py you provided returns the list directly, 
        # the calling code (external_api_connector.py) expects: data['updates'].
        return jsonify({"updates": filtered_data})
    else:
        # This will now correctly return the 404 for US-NY/UK as intended by the mock server.
        return jsonify({"message": f"No mock data found for jurisdiction: {code}"}), 404

@app.route('/')
def index():
    """
    Simple health check or landing page for the mock service.
    """
    print(f"--- Received request for: {request.path}")
    return "Mock Regulatory Service is UP and serving feed data via /feed!"

if __name__ == '__main__':
    # Running on all interfaces (0.0.0.0) and the exposed port (8080)
    app.run(host='0.0.0.0', port=8080, debug=False)
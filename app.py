import os
import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

# Store campaigns in memory (use database for production)
campaigns = {}
campaign_id_counter = 1

# ============================================
# SMM API HELPER (NO CORS ISSUES!)
# ============================================

SMM_API_URL = "https://yoyomedia.in/api/v2"
SMM_API_KEY = "0a54904459a7d42f090140d68a947e00fd38661c8454d4630dd76716b2d54337"

def call_smm_api(action, params):
    """Call SMM panel API directly from server - NO CORS!"""
    url = f"{SMM_API_URL}?key={SMM_API_KEY}&action={action}"
    for key, value in params.items():
        url += f"&{key}={value}"
    
    try:
        response = requests.get(url, timeout=30)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def place_order(service_id, link, quantity):
    """Place real order on SMM panel"""
    return call_smm_api("add", {
        "service": service_id,
        "link": link,
        "quantity": quantity
    })

def get_balance():
    """Get account balance"""
    result = call_smm_api("balance", {})
    return result.get("balance", 0)

# ============================================
# CAMPAIGN WORKER (RUNS IN BACKGROUND)
# ============================================

def campaign_worker():
    """Background thread that processes campaigns 24/7"""
    while True:
        try:
            now = time.time()
            for camp_id, campaign in list(campaigns.items()):
                if campaign["status"] != "running":
                    continue
                
                # Check if it's time for next drip
                if campaign["next_execution"] <= now:
                    # Calculate random quantity
                    import random
                    quantity = random.randint(campaign["min_val"], campaign["max_val"])
                    quantity = min(quantity, campaign["remaining"])
                    
                    if quantity <= 0:
                        campaign["status"] = "completed"
                        campaign["logs"].append(f"[{datetime.now()}] ✅ CAMPAIGN COMPLETE!")
                        continue
                    
                    # Place order
                    result = place_order(campaign["service_id"], campaign["link"], quantity)
                    
                    if "order" in result or "order_id" in result:
                        campaign["delivered"] += quantity
                        campaign["remaining"] -= quantity
                        campaign["order_count"] += 1
                        campaign["logs"].append(f"[{datetime.now()}] ✅ +{quantity} views (Order #{result.get('order', result.get('order_id'))})")
                        campaign["logs"] = campaign["logs"][-20:]  # Keep last 20 logs
                        
                        if campaign["remaining"] <= 0:
                            campaign["status"] = "completed"
                            campaign["logs"].append(f"[{datetime.now()}] 🏆 CAMPAIGN COMPLETE!")
                        else:
                            # Schedule next drip
                            campaign["next_execution"] = now + (campaign["interval_min"] * 60)
                    else:
                        campaign["logs"].append(f"[{datetime.now()}] ❌ Order failed: {result.get('error', 'Unknown')}")
                        campaign["logs"] = campaign["logs"][-20:]
            
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(10)

# Start background worker
threading.Thread(target=campaign_worker, daemon=True).start()

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/balance', methods=['GET'])
def api_balance():
    balance = get_balance()
    return jsonify({"success": True, "balance": balance})

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    return jsonify({"success": True, "campaigns": list(campaigns.values())})

@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    global campaign_id_counter
    data = request.json
    
    campaign = {
        "id": campaign_id_counter,
        "service_id": data["service_id"],
        "link": data["link"],
        "target": data["target"],
        "min_val": data["min_val"],
        "max_val": data["max_val"],
        "interval_min": data["interval_min"],
        "delivered": 0,
        "remaining": data["target"],
        "status": "running",
        "order_count": 0,
        "logs": [f"[{datetime.now()}] 🚀 Campaign created!"],
        "next_execution": time.time() + 5  # Start after 5 seconds
    }
    
    campaigns[campaign_id_counter] = campaign
    campaign_id_counter += 1
    
    return jsonify({"success": True, "campaign": campaign})

@app.route('/api/campaigns/<int:camp_id>', methods=['PUT'])
def update_campaign(camp_id):
    data = request.json
    if camp_id in campaigns:
        campaigns[camp_id]["status"] = data.get("status", campaigns[camp_id]["status"])
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Campaign not found"})

@app.route('/api/campaigns/<int:camp_id>', methods=['DELETE'])
def delete_campaign(camp_id):
    if camp_id in campaigns:
        del campaigns[camp_id]
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Campaign not found"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
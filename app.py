import os
import time
import threading
import random
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.')
CORS(app)

# Your SMM API
SMM_API_URL = "https://yoyomedia.in/api/v2"
SMM_API_KEY = "0a54904459a7d42f090140d68a947e00fd38661c8454d4630dd76716b2d54337"

# Store campaigns
campaigns = {}
campaign_id = 1

def call_api(action, params):
    """Call SMM API"""
    url = f"{SMM_API_URL}?key={SMM_API_KEY}&action={action}"
    for k, v in params.items():
        url += f"&{k}={v}"
    print(f"📡 Calling API: {url[:100]}...")
    try:
        response = requests.get(url, timeout=30)
        print(f"📡 Response: {response.text[:200]}")
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return {"error": str(e)}

def place_order(service_id, link, quantity):
    """Place real order"""
    print(f"📦 Placing order: {quantity} views for service {service_id}")
    return call_api("add", {
        "service": service_id,
        "link": link,
        "quantity": quantity
    })

def get_balance():
    """Get balance"""
    result = call_api("balance", {})
    return result.get("balance", 0)

# ============================================
# BACKGROUND WORKER - FIXED VERSION
# ============================================

def campaign_worker():
    """Background thread - runs every 2 seconds"""
    print("🚀 Worker thread started!")
    last_log = time.time()
    
    while True:
        try:
            now = time.time()
            
            # Log every 30 seconds to show it's alive
            if now - last_log > 30:
                print(f"💓 Worker alive. Campaigns: {len(campaigns)}")
                last_log = now
            
            for camp_id, campaign in list(campaigns.items()):
                if campaign["status"] != "running":
                    continue
                
                if campaign["remaining"] <= 0:
                    if campaign["status"] != "completed":
                        campaign["status"] = "completed"
                        campaign["logs"].append(f"[{datetime.now()}] 🏆 CAMPAIGN COMPLETE!")
                        print(f"✅ Campaign #{camp_id} completed!")
                    continue
                
                # Check if it's time for next drip
                if campaign["next_execution"] <= now:
                    print(f"🎯 Executing drip for campaign #{camp_id}")
                    
                    # Calculate random quantity
                    qty = random.randint(campaign["min_val"], campaign["max_val"])
                    qty = min(qty, campaign["remaining"])
                    
                    if qty <= 0:
                        continue
                    
                    # Place order
                    result = place_order(campaign["service_id"], campaign["link"], qty)
                    
                    if "order" in result or "order_id" in result:
                        campaign["delivered"] += qty
                        campaign["remaining"] -= qty
                        campaign["order_count"] += 1
                        order_id = result.get("order") or result.get("order_id")
                        campaign["logs"].append(f"[{datetime.now()}] ✅ +{qty} views (Order #{order_id})")
                        print(f"✅ Campaign #{camp_id}: +{qty} views ({campaign['delivered']}/{campaign['target']})")
                        
                        if campaign["remaining"] <= 0:
                            campaign["status"] = "completed"
                            campaign["logs"].append(f"[{datetime.now()}] 🏆 CAMPAIGN COMPLETE!")
                        else:
                            # Schedule next drip
                            campaign["next_execution"] = now + (campaign["interval"] * 60)
                            print(f"⏰ Next drip in {campaign['interval']} minutes")
                    else:
                        error_msg = result.get("error", "Unknown error")
                        campaign["logs"].append(f"[{datetime.now()}] ❌ Order failed: {error_msg}")
                        print(f"❌ Order failed for campaign #{camp_id}: {error_msg}")
                    
                    # Keep only last 20 logs
                    campaign["logs"] = campaign["logs"][-20:]
            
            time.sleep(2)  # Check every 2 seconds for faster response
            
        except Exception as e:
            print(f"❌ Worker error: {e}")
            time.sleep(10)

# Start worker
worker_thread = threading.Thread(target=campaign_worker, daemon=True)
worker_thread.start()
print("✅ Worker thread started")

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/balance', methods=['GET'])
def api_balance():
    try:
        balance = get_balance()
        return jsonify({"success": True, "balance": balance})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/campaigns', methods=['GET'])
def get_campaigns():
    return jsonify({"success": True, "campaigns": list(campaigns.values())})

@app.route('/api/campaigns', methods=['POST'])
def create_campaign():
    global campaign_id
    data = request.json
    print(f"📝 Creating campaign: {data}")
    
    campaign = {
        "id": campaign_id,
        "service_id": data["service_id"],
        "link": data["link"],
        "target": data["target"],
        "min_val": data["min_val"],
        "max_val": data["max_val"],
        "interval": data["interval"],
        "delivered": 0,
        "remaining": data["target"],
        "status": "running",
        "order_count": 0,
        "logs": [f"[{datetime.now()}] 🚀 Campaign created!"],
        "next_execution": time.time() + 5  # Start after 5 seconds
    }
    
    campaigns[campaign_id] = campaign
    print(f"✅ Campaign #{campaign_id} created! Will start in 5 seconds")
    campaign_id += 1
    
    return jsonify({"success": True, "campaign": campaign})

@app.route('/api/campaigns/<int:camp_id>', methods=['PUT'])
def update_campaign(camp_id):
    data = request.json
    if camp_id in campaigns:
        campaigns[camp_id]["status"] = data.get("status")
        print(f"📝 Campaign #{camp_id} status updated to: {data.get('status')}")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Campaign not found"})

@app.route('/api/campaigns/<int:camp_id>', methods=['DELETE'])
def delete_campaign(camp_id):
    if camp_id in campaigns:
        del campaigns[camp_id]
        print(f"🗑️ Campaign #{camp_id} deleted")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Campaign not found"})

if __name__ == '__main__':
    print("🚀 Starting Flask server on port 8080...")
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)

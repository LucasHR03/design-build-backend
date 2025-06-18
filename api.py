# ----- Flask API med manuel database og algoritme for ve-registrering -----

from flask import Flask, request, Response
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import mysql.connector
import bcrypt
import uuid
import os
from dotenv import load_dotenv

# ----- Indlæs miljøvariabler -----
load_dotenv(dotenv_path='miljø.env')

# ----- Flask setup -----
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ----- Forbind til allerede oprettet database -----
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor(dictionary=True)

# ----- Hjælpemetoder -----
def parse_xml(data):
    return ET.fromstring(data)

def make_xml_response(tag, content):
    root = ET.Element("Response")
    child = ET.SubElement(root, tag)
    child.text = str(content)
    return Response(ET.tostring(root), mimetype='application/xml')

def log_handling(bruger_id, handling, detaljer):
    cursor.execute("""
        INSERT INTO BehandlingsLog (bruger_id, handling, detaljer)
        VALUES (%s, %s, %s)
    """, (bruger_id, handling, detaljer))
    conn.commit()

def hent_bruger_id_fra_token(token):
    cursor.execute("""
        SELECT bruger_id FROM Session 
        WHERE session_token = %s AND udløbs_tidspunkt > NOW()
    """, (token,))
    resultat = cursor.fetchone()
    return resultat['bruger_id'] if resultat else None

def beregn_interval_forrige(bruger_id, start_tid):
    cursor.execute("""
        SELECT slut_tidspunkt FROM VeRegistrering
        WHERE bruger_id = %s AND slut_tidspunkt < %s
        ORDER BY slut_tidspunkt DESC LIMIT 1
    """, (bruger_id, start_tid))
    forrige = cursor.fetchone()
    if forrige:
        forskel = (start_tid - forrige['slut_tidspunkt']).total_seconds()
        return int(forskel)
    return None

def tjek_for_tre_veer_under_tre_minutter(bruger_id):
    cursor.execute("""
        SELECT slut_tidspunkt, start_tidspunkt FROM VeRegistrering
        WHERE bruger_id = %s
        ORDER BY start_tidspunkt DESC
        LIMIT 3
    """, (bruger_id,))
    veer = cursor.fetchall()
    if len(veer) < 3:
        return False

    interval1 = (veer[0]['start_tidspunkt'] - veer[1]['slut_tidspunkt']).total_seconds()
    interval2 = (veer[1]['start_tidspunkt'] - veer[2]['slut_tidspunkt']).total_seconds()

    return interval1 <= 180 and interval2 <= 180

# ----- Endpoints -----
@app.route('/api/login', methods=['POST'])
def login():
    cursor.execute("DELETE FROM Session WHERE udløbs_tidspunkt < NOW()")
    conn.commit()

    root = parse_xml(request.data)
    cpr = root.findtext("CPR")
    pin = root.findtext("PIN")

    cursor.execute("SELECT * FROM Bruger WHERE cpr = %s", (cpr,))
    bruger = cursor.fetchone()

    if bruger:
        gemt_hash = bruger['pin_kode_hash'].encode('utf-8')
        if bcrypt.checkpw(pin.encode('utf-8'), gemt_hash):
            session_token = str(uuid.uuid4())
            udløb = datetime.now() + timedelta(hours=2)
            cursor.execute("""
                INSERT INTO Session (bruger_id, session_token, udløbs_tidspunkt)
                VALUES (%s, %s, %s)
            """, (bruger['bruger_id'], session_token, udløb))
            conn.commit()
            log_handling(bruger['bruger_id'], "Login", "Bruger loggede ind")
            return make_xml_response("Token", session_token)

    return make_xml_response("Message", "Login failed"), 401

@app.route('/api/gem-ve', methods=['POST'])
def gem_ve():
    root = parse_xml(request.data)
    token = root.findtext("Token")
    bruger_id = hent_bruger_id_fra_token(token)

    if not bruger_id:
        return make_xml_response("Message", "Token ugyldig eller udløbet"), 401

    try:
        start_ts = root.findtext("StartTimestamp")
        stop_ts = root.findtext("StopTimestamp")
        duration = root.findtext("Duration")

        h, m, s = map(int, duration.split(":"))
        duration_sec = h * 3600 + m * 60 + s

        start_dt = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
        stop_dt = datetime.strptime(stop_ts, "%Y-%m-%d %H:%M:%S")

        interval_sec = beregn_interval_forrige(bruger_id, start_dt)

        cursor.execute("""
            INSERT INTO VeRegistrering (bruger_id, start_tidspunkt, slut_tidspunkt, varighed, interval_til_naeste)
            VALUES (%s, %s, %s, %s, %s)
        """, (bruger_id, start_dt, stop_dt, duration_sec, interval_sec))
        conn.commit()

        log_handling(bruger_id, "Ve-registrering",
                     f"Start: {start_ts}, Slut: {stop_ts}, Varighed: {duration_sec}, Interval: {interval_sec}")

        advarsel = ""
        if tjek_for_tre_veer_under_tre_minutter(bruger_id):
            advarsel = "ADVARSEL: Veerne kommer meget hyppigt – kontakt fødeafdeling"
            tidspunkt = datetime.now()
            cursor.execute("""
                INSERT INTO Noter (bruger_id, tidspunkt, noter_type, beskrivelse)
                VALUES (%s, %s, %s, %s)
            """, (bruger_id, tidspunkt, "Advarsel", advarsel))
            conn.commit()
            log_handling(bruger_id, "Advarsel", advarsel)

        return make_xml_response("Message", advarsel or "Ve registreret")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500

@app.route('/api/opret-bruger', methods=['POST'])
def opret_bruger():
    try:
        root = parse_xml(request.data)
        cpr = root.findtext("CPR")
        navn = root.findtext("Navn")
        pin = root.findtext("PIN")

        cursor.execute("SELECT * FROM Bruger WHERE cpr = %s", (cpr,))
        if cursor.fetchone():
            return make_xml_response("Message", "Bruger findes allerede"), 409

        hashed_pin = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cursor.execute("""
            INSERT INTO Bruger (cpr, navn, pin_kode_hash)
            VALUES (%s, %s, %s)
        """, (cpr, navn, hashed_pin))
        conn.commit()

        cursor.execute("SELECT LAST_INSERT_ID() AS id")
        bruger_id = cursor.fetchone()["id"]
        log_handling(bruger_id, "Brugeroprettelse", f"Oprettet: {navn}")

        return make_xml_response("Message", "Bruger oprettet")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    root = parse_xml(request.data)
    token = root.findtext("Token")

    cursor.execute("DELETE FROM Session WHERE session_token = %s", (token,))
    if cursor.rowcount > 0:
        conn.commit()
        return make_xml_response("Message", "Logget ud")
    else:
        return make_xml_response("Message", "Ugyldig eller udløbet token"), 400

@app.route('/api/gem-note', methods=['POST'])
def gem_note():
    root = parse_xml(request.data)
    token = root.findtext("Token")

    bruger_id = hent_bruger_id_fra_token(token)
    if not bruger_id:
        return make_xml_response("Message", "Token ugyldig eller udløbet"), 401

    noter_type = root.findtext("Type") or "Note"
    beskrivelse = root.findtext("Beskrivelse")

    if not beskrivelse:
        return make_xml_response("Message", "Beskrivelse mangler"), 400

    tidspunkt = datetime.now()
    try:
        cursor.execute("""
            INSERT INTO Noter (bruger_id, tidspunkt, noter_type, beskrivelse)
            VALUES (%s, %s, %s, %s)
        """, (bruger_id, tidspunkt, noter_type, beskrivelse))
        conn.commit()
        log_handling(bruger_id, "Note tilføjet", f"{noter_type}: {beskrivelse}")
        return make_xml_response("Message", "Note gemt")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500

# ----- Start server -----
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5050, debug=True)
from flask import Flask, request, Response
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import mysql.connector
import bcrypt
from cryptography.fernet import Fernet
import uuid
import os
from dotenv import load_dotenv

# ----- Indlæs miljøvariabler -----
load_dotenv(dotenv_path='miljø.env')  # Læs miljøfilen

# ----- Kryptering -----
fernet = Fernet(os.getenv("FERNET_KEY").encode())

# ----- Flask app setup -----
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)
cursor = conn.cursor(dictionary=True)

# ----- Hjælpefunktioner -----
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

# ----- Endpoints -----
@app.route('/api/login', methods=['POST'])
def login():
    # Ryd udløbne sessions først
    cursor.execute("DELETE FROM Session WHERE udløbs_tidspunkt < NOW()")
    conn.commit()

    root = parse_xml(request.data)
    cpr = root.findtext("CPR")
    pin = root.findtext("PIN")

    encrypted_cpr = fernet.encrypt(cpr.encode()).decode()

    cursor.execute("SELECT * FROM Bruger WHERE cpr_krypteret=%s", (encrypted_cpr,))
    bruger = cursor.fetchone()

    if bruger:
        gemt_hash = bruger['pin_kode_hash'].encode('utf-8')
        if bcrypt.checkpw(pin.encode('utf-8'), gemt_hash):
            session_token = str(uuid.uuid4())
            udløb = datetime.now() + timedelta(hours=2)
            cursor.execute(
                "INSERT INTO Session (bruger_id, session_token, udløbs_tidspunkt) VALUES (%s, %s, %s)",
                (bruger['bruger_id'], session_token, udløb)
            )
            conn.commit()
            log_handling(bruger['bruger_id'], "Login", "Bruger loggede ind via appen")
            return make_xml_response("Token", session_token)

    return make_xml_response("Message", "Login failed"), 401

@app.route('/api/gem-ve', methods=['POST'])
def gem_ve():
    root = ET.fromstring(request.data)
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

        cursor.execute(
            "INSERT INTO VeRegistrering (bruger_id, start_tidspunkt, slut_tidspunkt, varighed) VALUES (%s, %s, %s, %s)",
            (bruger_id, start_ts, stop_ts, duration_sec)
        )
        conn.commit()

        log_handling(bruger_id, "Ve-registrering",
                     f"Start: {start_ts}, Slut: {stop_ts}, Varighed: {duration_sec} sek")

        return make_xml_response("Message", "Ve registreret")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500


@app.route('/api/opret-bruger', methods=['POST'])
def opret_bruger():
    try:
        root = ET.fromstring(request.data)
        cpr = root.findtext("CPR")
        navn = root.findtext("Navn")
        pin = root.findtext("PIN")

        encrypted_cpr = fernet.encrypt(cpr.encode()).decode()

        cursor.execute("SELECT * FROM Bruger WHERE cpr_krypteret = %s", (encrypted_cpr,))
        if cursor.fetchone():
            return make_xml_response("Message", "Bruger findes allerede"), 409

        hashed_pin = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor.execute(
            "INSERT INTO Bruger (cpr_krypteret, navn, pin_kode_hash) VALUES (%s, %s, %s)",
            (encrypted_cpr, navn, hashed_pin)
        )
        conn.commit()

        cursor.execute("SELECT LAST_INSERT_ID() AS id")
        bruger_id = cursor.fetchone()["id"]

        log_handling(bruger_id, "Brugeroprettelse", f"Oprettet bruger: {navn}")

        return make_xml_response("Message", "Bruger oprettet")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500
    
@app.route('/api/logout', methods=['POST'])
def logout():
    root = parse_xml(request.data)
    token = root.findtext("Token")

    # Find og slet sessionen
    cursor.execute("DELETE FROM Session WHERE session_token = %s", (token,))
    if cursor.rowcount > 0:
        conn.commit()
        return make_xml_response("Message", "Logget ud")
    else:
        return make_xml_response("Message", "Ugyldig eller allerede udløbet token"), 400

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
        cursor.execute(
            "INSERT INTO Noter (bruger_id, tidspunkt, noter_type, beskrivelse) VALUES (%s, %s, %s, %s)",
            (bruger_id, tidspunkt, noter_type, beskrivelse)
        )
        conn.commit()
        log_handling(bruger_id, "Note tilføjet", f"Type: {noter_type}, Beskrivelse: {beskrivelse}")
        return make_xml_response("Message", "Note gemt")
    except Exception as e:
        return make_xml_response("Error", str(e)), 500


if __name__ == '__main__':
    # Hardcoded testbruger - kan fjernes hvis der kan oprettes brugere via API'en 
    test_cpr = "1234567890"
    test_navn = "Test Bruger"
    test_pin = "1234"

    encrypted_cpr = fernet.encrypt(test_cpr.encode()).decode()
    hashed_pin = bcrypt.hashpw(test_pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Tjek om brugeren findes
    cursor.execute("SELECT * FROM Bruger")
    eksisterende = cursor.fetchall()
    findes_allerede = False

    for bruger in eksisterende:
        try:
            dekrypteret = fernet.decrypt(bruger['cpr_krypteret'].encode()).decode()
            if dekrypteret == test_cpr:
                findes_allerede = True
                break
        except Exception:
            continue

    # Opret hvis ikke fundet
    if not findes_allerede:
        cursor.execute(
            "INSERT INTO Bruger (cpr_krypteret, navn, pin_kode_hash) VALUES (%s, %s, %s)",
            (encrypted_cpr, test_navn, hashed_pin)
        )
        conn.commit()
        print("Testbruger oprettet.")
    else:
        print("Testbruger findes allerede.")

    app.run(debug=True)

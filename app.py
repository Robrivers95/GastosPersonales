import os
import json
from flask import Flask, request, jsonify, render_template
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, firestore

# -----------------------
# CONFIGURACIÓN
# -----------------------
basedir = os.path.abspath(os.path.dirname(__file__))

# Inicializa Firebase
cred = credentials.Certificate(os.path.join(basedir, 'serviceAccountKey.json'))
firebase_admin.initialize_app(cred)
db = firestore.client()

# Inicializa OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # exporta esta var en tu shell
client = OpenAI(api_key=OPENAI_API_KEY)

app = Flask(__name__, template_folder='templates', static_folder='static')

# -----------------------
# RUTAS
# -----------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/addExpense', methods=['POST'])
def add_expense():
    data = request.json or {}
    texto = data.get('texto', '').strip()
    usuario = data.get('usuario', '').strip()
    if not texto or not usuario:
        return jsonify({"error": "falta texto o usuario"}), 400

    # Llamada a OpenAI para extraer JSON
    prompt = (
        f"Extrae del siguiente texto en formato JSON con claves "
        f'{{fecha:"dd/mm/aaaa", concepto:"", monto:0, proyecto:""}}:\n"{texto}"'
    )
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}],
        temperature=0
    )
    raw = resp.choices[0].message.content.strip()
    try:
        gasto = json.loads(raw)
    except Exception as e:
        return jsonify({"error": "JSON inválido", "raw": raw}), 500

    # Guarda en Firestore
    doc = {
        "fecha": gasto.get("fecha"),
        "concepto": gasto.get("concepto"),
        "monto": gasto.get("monto"),
        "proyecto": gasto.get("proyecto"),
        "usuario": usuario,
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    db.collection("gastos").add(doc)
    return jsonify({"success": True, "gasto": gasto})


@app.route('/api/listExpenses', methods=['GET'])
def list_expenses():
    docs = db.collection("gastos").order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    out = []
    for d in docs:
        rec = d.to_dict()
        rec['id'] = d.id
        out.append(rec)
    return jsonify(out)


# (Opcional) endpoints para usuarios y conceptos:
@app.route('/api/listUsers', methods=['GET'])
def list_users():
    docs = db.collection("usuarios").stream()
    return jsonify([{"id":d.id, **d.to_dict()} for d in docs])

@app.route('/api/listConcepts', methods=['GET'])
def list_concepts():
    docs = db.collection("conceptos").stream()
    return jsonify([{"id":d.id, **d.to_dict()} for d in docs])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

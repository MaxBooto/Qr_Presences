import mysql.connector
import qrcode
from datetime import datetime
import os
from flask import Flask, render_template, request, send_file, jsonify
from io import BytesIO
import pandas as pd
from flask_mail import Mail, Message

app = Flask(__name__)

# Configuration de la connexion à la base de données MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'qr_presence'
}

# Configuration de Flask-Mail
#Utilisez votre mail pour creer le password des applications
app.config['MAIL_SERVER'] = ''
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = ''  
app.config['MAIL_PASSWORD'] = ''  
app.config['MAIL_DEFAULT_SENDER'] = ''

mail = Mail(app)

# Dossier pour stocker les QR codes temporaires
if not os.path.exists('qrcodes'):
    os.makedirs('qrcodes')

# Ajouter ou modifier un étudiant
def ajouter_ou_modifier_etudiant(matricule, nom, postnom, prenom, sexe, promotion, systeme, email, is_update=False):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        if is_update:
            cursor.execute("""
                UPDATE etudiants SET nom=%s, postnom=%s, prenom=%s, sexe=%s, promotion=%s, systeme=%s, email=%s
                WHERE matricule=%s
            """, (nom, postnom, prenom, sexe, promotion, systeme, email, matricule))
        else:
            cursor.execute("""
                INSERT INTO etudiants (matricule, nom, postnom, prenom, sexe, promotion, systeme, email)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (matricule, nom, postnom, prenom, sexe, promotion, systeme, email))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"Erreur lors de l'opération sur l'étudiant : {err}")
        return False

# Supprimer un étudiant
def supprimer_etudiant(matricule):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM presences WHERE etudiant_id = %s", (matricule,))
        cursor.execute("DELETE FROM etudiants WHERE matricule = %s", (matricule,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except mysql.connector.Error as err:
        print(f"Erreur lors de la suppression de l'étudiant : {err}")
        return False

# Générer un QR code et retourner un buffer
def generer_qr_code_image(matricule):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(matricule)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

# Récupérer la liste des étudiants
def get_etudiants():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT matricule, nom, postnom, prenom, sexe, promotion, systeme, email FROM etudiants")
        students = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{
            'matricule': s[0], 'nom': s[1], 'postnom': s[2], 'prenom': s[3],
            'sexe': s[4], 'promotion': s[5], 'systeme': s[6], 'email': s[7]
        } for s in students]
    except mysql.connector.Error as err:
        print(f"Erreur lors de la récupération des étudiants : {err}")
        return []

# Récupérer la liste des présences
def get_presences(date=None):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = """
            SELECT e.nom, e.postnom, e.prenom, p.date_presence, e.promotion, e.systeme
            FROM presences p
            JOIN etudiants e ON p.etudiant_id = e.matricule
        """
        params = []
        if date:
            query += " WHERE DATE(p.date_presence) = %s"
            params = (date,)
        query += " ORDER BY p.date_presence DESC"
        cursor.execute(query, params)
        presences = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{
            'nom': p[0], 'postnom': p[1], 'prenom': p[2], 'date_presence': p[3].strftime('%Y-%m-%d %H:%M:%S'),
            'promotion': p[4], 'systeme': p[5]
        } for p in presences]
    except mysql.connector.Error as err:
        print(f"Erreur lors de la récupération des présences : {err}")
        return []

# Exporter les étudiants en Excel
def export_etudiants():
    students = get_etudiants()
    df = pd.DataFrame(students)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer

# Exporter les présences en Excel
def export_presences(date=None):
    presences = get_presences(date)
    df = pd.DataFrame(presences)
    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)
    return buffer

# Routes Flask
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/etudiant')
def etudiant():
    return render_template('etudiant.html')

@app.route('/ajout_student')
def ajout_student():
    matricule = request.args.get('matricule', '')
    return render_template('ajout_student.html', matricule=matricule)

@app.route('/presences')
def presences():
    return render_template('presences.html')

@app.route('/historique')
def historique():
    return render_template('historique.html')

@app.route('/api/etudiants')
def api_etudiants():
    return jsonify(get_etudiants())

@app.route('/api/etudiant', methods=['POST'])
def api_ajouter_etudiant():
    data = request.json
    success = ajouter_ou_modifier_etudiant(
        data['matricule'], data['nom'], data['postnom'], data['prenom'],
        data['sexe'], data['promotion'], data['systeme'], data.get('email', '')
    )
    return jsonify({
        'success': success,
        'message': 'Étudiant ajouté avec succès.' if success else 'Erreur lors de l\'ajout de l\'étudiant.'
    })

@app.route('/api/etudiant/<matricule>', methods=['GET', 'PUT', 'DELETE'])
def api_etudiant(matricule):
    if request.method == 'GET':
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT matricule, nom, postnom, prenom, sexe, promotion, systeme, email FROM etudiants WHERE matricule = %s",
                (matricule,))
            student = cursor.fetchone()
            cursor.fetchall()
            cursor.close()
            conn.close()
            if student:
                return jsonify({
                    'matricule': student[0], 'nom': student[1], 'postnom': student[2],
                    'prenom': student[3], 'sexe': student[4], 'promotion': student[5],
                    'systeme': student[6], 'email': student[7]
                })
            return jsonify({'success': False, 'message': 'Étudiant non trouvé.'}), 404
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'message': f'Erreur : {err}'}), 500
    elif request.method == 'PUT':
        data = request.json
        success = ajouter_ou_modifier_etudiant(
            matricule, data['nom'], data['postnom'], data['prenom'],
            data['sexe'], data['promotion'], data['systeme'], data.get('email', ''), is_update=True
        )
        return jsonify({
            'success': success,
            'message': 'Étudiant modifié avec succès.' if success else 'Erreur lors de la modification de l\'étudiant.'
        })
    elif request.method == 'DELETE':
        success = supprimer_etudiant(matricule)
        return jsonify({
            'success': success,
            'message': 'Étudiant supprimé avec succès.' if success else 'Erreur lors de la suppression de l\'étudiant.'
        })

@app.route('/generer_et_envoyer_qr', methods=['POST'])
def generer_et_envoyer_qr():
    data = request.json
    matricule = data.get('matricule')
    email = data.get('email')
    
    if not matricule or not email:
        return jsonify({'success': False, 'message': 'Matricule ou e-mail non fourni.'}), 400
    
    try:
        # Générer le QR code
        buffer = generer_qr_code_image(matricule)
        
        # Créer l'e-mail
        msg = Message(
            subject=f"QR Code pour l'étudiant {matricule}",
            recipients=[email],
            body=f"Bonjour,\n\nVeuillez trouver en pièce jointe le QR code pour l'étudiant avec le matricule {matricule}.\n\nCordialement,\nVotre système de gestion des présences"
        )
        msg.attach(f"qr_{matricule}.png", "image/png", buffer.getvalue())
        
        # Envoyer l'e-mail
        mail.send(msg)
        
        # Permettre également le téléchargement du QR code
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"qr_{matricule}.png",
            mimetype='image/png'
        )
    except Exception as err:
        print(f"Erreur lors de la génération ou de l'envoi du QR code : {err}")
        return jsonify({'success': False, 'message': 'Erreur lors de la génération ou de l\'envoi du QR code.'}), 500

@app.route('/api/presences')
def api_presences():
    date = request.args.get('date')
    return jsonify(get_presences(date))

@app.route('/api/presence/<matricule>')
def api_presence(matricule):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.nom, e.postnom, e.prenom, p.date_presence, e.promotion, e.systeme
            FROM presences p
            JOIN etudiants e ON p.etudiant_id = e.matricule
            WHERE p.etudiant_id = %s
            ORDER BY p.date_presence DESC LIMIT 1
        """, (matricule,))
        presence = cursor.fetchone()
        cursor.fetchall()
        cursor.close()
        conn.close()
        if presence:
            return jsonify({
                'success': True,
                'data': {
                    'nom': presence[0],
                    'postnom': presence[1],
                    'prenom': presence[2],
                    'date_presence': presence[3].strftime('%Y-%m-%d %H:%M:%S'),
                    'promotion': presence[4],
                    'systeme': presence[5]
                }
            })
        return jsonify({'success': False, 'message': 'Présence non trouvée.'}), 404
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erreur : {err}'}), 500

@app.route('/api/scan_qr', methods=['POST'])
def scan_qr():
    data = request.json
    matricule = data.get('matricule')
    if not matricule:
        return jsonify({'success': False, 'message': 'Matricule non fourni.'}), 400
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT date_presence FROM presences 
            WHERE etudiant_id = %s 
            AND date_presence > NOW() - INTERVAL 5 MINUTE
        """, (matricule,))
        recent_presence = cursor.fetchone()
        cursor.fetchall()
        if recent_presence:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Présence récente pour {matricule}, ignorée.'}), 400
        cursor.execute("SELECT matricule FROM etudiants WHERE matricule = %s", (matricule,))
        result = cursor.fetchone()
        cursor.fetchall()
        if result:
            date_presence = datetime.now()
            cursor.execute("INSERT INTO presences (etudiant_id, date_presence) VALUES (%s, %s)", 
                          (matricule, date_presence))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': f'Présence enregistrée pour {matricule}'})
        cursor.close()
        conn.close()
        return jsonify({'success': False, 'message': f'Matricule {matricule} non trouvé.'}), 404
    except mysql.connector.Error as err:
        return jsonify({'success': False, 'message': f'Erreur : {err}'}), 500

@app.route('/api/export_etudiants')
def export_etudiants_route():
    buffer = export_etudiants()
    return send_file(buffer, as_attachment=True, download_name='etudiants.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/api/export_presences')
def export_presences_route():
    date = request.args.get('date')
    buffer = export_presences(date)
    return send_file(buffer, as_attachment=True, download_name=f'presences_{date or "all"}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    app.run(debug=True)
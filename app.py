import mysql.connector
import qrcode
from datetime import datetime
import os
from flask import Flask, redirect,render_template, request, send_file, jsonify
from io import BytesIO
import pandas as pd
import io
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import qrcode
from datetime import datetime


app = Flask(__name__)

# Configuration de la connexion à la base de données MySQL
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'qr_presencess'
}

# Dossier pour stocker les QR codes temporaires
if not os.path.exists('qrcodes'):
    os.makedirs('qrcodes')

# Ajouter ou modifier un étudiant
def ajouter_ou_modifier_etudiant(matricule, nom, postnom, prenom, sexe, promotion, systeme, is_update=False):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        if is_update:
            cursor.execute("""
                UPDATE etudiants SET nom=%s, postnom=%s, prenom=%s, sexe=%s, promotion=%s, systeme=%s
                WHERE matricule=%s
            """, (nom, postnom, prenom, sexe, promotion, systeme, matricule))
        else:
            cursor.execute("""
                INSERT INTO etudiants (matricule, nom, postnom, prenom, sexe, promotion, systeme)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (matricule, nom, postnom, prenom, sexe, promotion, systeme))
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

# Générer un QR code et l'enregistrer en PNG
def generer_qr_code_image(matricule):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(matricule)
    qr.make(fit=True)
    qr_img = qr.make_image(fill='black', back_color='white')
    file_path = f'qrcodes/qr_{matricule}.png'
    qr_img.save(file_path)
    return file_path

# Récupérer la liste des étudiants
def get_etudiants():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT matricule, nom, postnom, prenom, sexe, promotion, systeme FROM etudiants")
        students = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{
            'matricule': s[0], 'nom': s[1], 'postnom': s[2], 'prenom': s[3],
            'sexe': s[4], 'promotion': s[5], 'systeme': s[6]
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
        data['sexe'], data['promotion'], data['systeme']
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
                "SELECT matricule, nom, postnom, prenom, sexe, promotion, systeme FROM etudiants WHERE matricule = %s",
                (matricule,))
            student = cursor.fetchone()
            cursor.fetchall()
            cursor.close()
            conn.close()
            if student:
                return jsonify({
                    'matricule': student[0], 'nom': student[1], 'postnom': student[2],
                    'prenom': student[3], 'sexe': student[4], 'promotion': student[5], 'systeme': student[6]
                })
            return jsonify({'success': False, 'message': 'Étudiant non trouvé.'}), 404
        except mysql.connector.Error as err:
            return jsonify({'success': False, 'message': f'Erreur : {err}'}), 500
    elif request.method == 'PUT':
        data = request.json
        success = ajouter_ou_modifier_etudiant(
            matricule, data['nom'], data['postnom'], data['prenom'],
            data['sexe'], data['promotion'], data['systeme'], is_update=True
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

@app.route('/generer_qr', methods=['GET'])
def generer_qr():
    matricule = request.args.get('matricule')
    if not matricule:
        return jsonify({'success': False, 'message': 'Erreur : Matricule non fourni.'}), 400
    try:
        file_path = generer_qr_code_image(matricule)
        return send_file(file_path, as_attachment=True, download_name=f"qr_{matricule}.png", mimetype='image/png')
    except Exception as err:
        print(f"Erreur lors de la génération du QR code : {err}")
        return jsonify({'success': False, 'message': 'Erreur lors de la génération du QR code.'}), 500

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

@app.route('/exam_schedule')
def exam_schedule():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM exam_schedule ORDER BY exam_date, exam_time")
    schedules = cursor.fetchall()
    cursor.close()
    return render_template('exam_schedule.html', schedules=schedules)


@app.route('/add_exam_schedule/add', methods=['GET', 'POST'])
def add_exam_schedule():
    if request.method == 'POST':
        promotion = request.form['promotion']
        departement = request.form['departement']
        option_ = request.form.get('option', None)
        exam_date = request.form['exam_date']
        exam_time = request.form['exam_time']
        subject = request.form['subject']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO exam_schedule (promotion, departement, option_, exam_date, exam_time, subject)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (promotion, departement, option_, exam_date, exam_time, subject))
        
        conn.commit()
        cursor.close()
        return redirect('/exam_schedule')

    # données promotion, département, option pour formulaire
    promotions = ['L2 LMD', 'L3 LMD', 'L4 LMD', 'L2 AS']
    departements = ['Informatique', 'Mathématiques', 'Physique', 'Chimie']  # adapte à ton contexte
    options = ['Option A', 'Option B', 'Option C']  # adapte ou rends dynamique
    return render_template('add_exam_schedule.html', promotions=promotions, departements=departements, options=options)

@app.route('/add_student', methods=['GET', 'POST'])
def add_student():
    if request.method == 'POST':
        nom = request.form['nom']
        postnom = request.form['postnom']
        prenom = request.form['prenom']
        matricule = request.form['matricule']
        promotion = request.form['promotion']
        departement = request.form.get('departement', None)
        option_ = request.form.get('option', None)

        # vérifier conditions
        if promotion in ['L2 LMD', 'L3 LMD', 'L4 LMD', 'L2 AS'] and not departement:
            return "Le département est obligatoire pour cette promotion", 400
        if promotion in ['L3 LMD', 'L4 LMD', 'L2 PADEM'] and not option_:
            return "L'option est obligatoire pour cette promotion", 400

        cursor = mysql.connector.cursor()
        cursor.execute("""
            INSERT INTO students (nom, postnom, prenom, matricule, promotion, departement, option_)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (nom, postnom, prenom, matricule, promotion, departement, option_))
        mysql.connector.commit()
        cursor.close()

        # Générer QR code (existant dans ton projet)
        # ...

        return redirect('/students')

    promotions = ['L2 LMD', 'L3 LMD', 'L4 LMD', 'L2 AS']
    departements = ['Informatique', 'Mathématiques', 'Physique', 'Chimie']
    options = ['Option A', 'Option B', 'Option C']
    return render_template('ajout_student.html', promotions=promotions, departements=departements, options=options)


@app.route('/print_enrollment/<matricule>')
def print_enrollment(matricule):
    cursor = mysql.connector.cursor()
    # Récupérer infos étudiant
    cursor.execute("SELECT nom, postnom, prenom, promotion, departement, option_ FROM students WHERE matricule = %s", (matricule,))
    etudiant = cursor.fetchone()
    if not etudiant:
        return "Étudiant non trouvé", 404

    nom, postnom, prenom, promotion, departement, option_ = etudiant

    # Récupérer horaires examens selon critères
    if promotion in ['L2 LMD']:
        cursor.execute("""
            SELECT exam_date, exam_time, subject FROM exam_schedule
            WHERE promotion = %s AND departement = %s
            ORDER BY exam_date, exam_time
        """, (promotion, departement))
    else:
        cursor.execute("""
            SELECT exam_date, exam_time, subject FROM exam_schedule
            WHERE promotion = %s AND departement = %s AND option_ = %s
            ORDER BY exam_date, exam_time
        """, (promotion, departement, option_))
    exams = cursor.fetchall()
    cursor.close()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # QR code en haut à gauche
    qr_img = qrcode.make(matricule)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)
    qr_reader = ImageReader(qr_buffer)
    c.drawImage(qr_reader, 40, height - 120, 80, 80)

    # Identité étudiant
    c.setFont("Helvetica-Bold", 14)
    c.drawString(140, height - 60, f"Fiche d'enrôlement")
    c.setFont("Helvetica", 12)
    c.drawString(140, height - 90, f"Nom: {nom} {postnom} {prenom}")
    c.drawString(140, height - 110, f"Promotion: {promotion}")
    c.drawString(140, height - 130, f"Département: {departement}")
    if option_:
        c.drawString(140, height - 150, f"Option: {option_}")

    # Titre horaires
    c.setFont("Helvetica-Bold", 13)
    c.drawString(40, height - 190, "Horaires d'examen:")

    c.setFont("Helvetica", 11)
    y = height - 210
    for exam_date, exam_time, subject in exams:
        date_str = exam_date.strftime('%d/%m/%Y') if isinstance(exam_date, datetime) else exam_date
        c.drawString(50, y, f"{date_str} à {exam_time} : {subject}")
        y -= 20
        if y < 50:
            c.showPage()
            y = height - 50

    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"fiche_enrolement_{matricule}.pdf", mimetype='application/pdf')


@app.route('/fiche_enrolement', methods=['GET', 'POST'])
def fiche_enrolement():
    if request.method == 'POST':
        matricule = request.form['matricule']

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Récupération de l'étudiant
        cursor.execute("SELECT * FROM etudiants WHERE matricule = %s", (matricule,))
        etudiant = cursor.fetchone()

        if not etudiant:
            return "Étudiant introuvable"

        a = etudiant[5] + ' ' + etudiant[8]
        print(a , type(a))
        print(etudiant[6])
        print(etudiant[7])
        

        # Récupération des horaires d'examen liés à sa promotion/département/option
        cursor.execute("""
            SELECT * FROM exam_schedule
            WHERE promotion ='""" + a +"""'""")



        #cursor.execute("""SELECT * FROM exam_schedule WHERE promotion = %s AND departement = %s AND (option_ = %s OR option_ IS NULL)""", (a, etudiant[6], etudiant[7]))


        horaires = cursor.fetchall()

        print(horaires)

        cursor.close()

        # Génération du QR code de l'étudiant (matricule)
        import qrcode
        import io
        import base64

        qr = qrcode.make(etudiant[0])
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return render_template('fiche_enrolement.html', etudiant=etudiant, horaires=horaires, qr_code=qr_code_base64)

    return render_template('choisir_etudiant.html')






if __name__ == '__main__':
    app.run(debug=True)
import datetime
import os
import shutil

import requests
from flask import Flask, render_template, url_for, json, redirect, request, jsonify
import base64
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_talisman import Talisman

import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'geojson'}

app = Flask(__name__)
app.secret_key = "*****************" # llave secreta de la app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

cred = credentials.Certificate('static/credentials/service_account.json') # google service_account para conexion con firebase
firebase_app = firebase_admin.initialize_app(cred)
db = firestore.client()

app.config[
    'SQLALCHEMY_DATABASE_URI'] = 'postgresql://*****************************************************************/postgres' # string de conexion para rds amazon postgres sql
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
dbsql = SQLAlchemy(app)
migrate = Migrate(app, dbsql)

IMGUR_CLIENT_ID = "*****************" # API key de IMGUR para guardar imagenes

class Estado(dbsql.Model):
    id = dbsql.Column(dbsql.Integer, primary_key=True)
    estado = dbsql.Column(dbsql.String, nullable=False)

    def __repr__(self):
        return f'<Estado {self.id} - {self.estado}>'


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/add_rows', methods=['POST'])
def add_rows():
    n = request.json['n']

    # Get the maximum id value in the table
    last_row = Estado.query.order_by(Estado.id.desc()).first()
    if last_row:
        start_id = last_row.id + 1
    else:
        start_id = 1

    # Add n rows to the table
    for i in range(start_id, start_id + n):
        new_row = Estado(id=i, estado="")
        dbsql.session.add(new_row)

    dbsql.session.commit()
    return jsonify({'message': f'{n} rows added'}), 201


@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No file part"}), 400

    files = request.files.getlist('image')

    image_urls = []

    for file in files:
        image_data = base64.b64encode(file.read())
        headers = {
            'Authorization': f'Client-ID {IMGUR_CLIENT_ID}',
        }
        data = {
            'image': image_data
        }

        response = requests.post('https://api.imgur.com/3/image', headers=headers, data=data)

        if response.status_code == 200:
            image_url = response.json().get('data').get('link')
            image_urls.append(image_url)

            doc_ref = db.collection(u'obras').document()
            doc_ref.set({
                u'url': image_url,
                u'timestamp': datetime.datetime.now(),
                u'usuario': request.form['usuario'],
                u'obra': request.form['obra'],
                u'observacion': request.form['observacion'],
                u'lat': request.form['lat'],
                u'long': request.form['long'],
            })
        else:
            return jsonify({"error": "Failed to upload image"}), 400

    return jsonify({"urls": image_urls}), 200

@app.route('/uploadfotos')
def uploadfotos():
    return render_template('uploadfotos.html')

@app.route('/uploadgeojsonlotes', methods=['GET', 'POST'])
def upload_file_geojson_lotes():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            oldfile = 'static/geojson/ig2.geojson'
            newfile = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            shutil.copyfile(newfile, oldfile)
            os.remove(newfile)
            return redirect(url_for('testupload', name=filename))


@app.route('/espacio')
def index():
    return render_template('espacios.html')


@app.route('/mapaarreglomicasa')
def mapa_arreglo_mi_casa():
    return render_template('mapaarreglomicasa.html')


@app.route('/sobrecbim')
def sobrecbim():
    return render_template('about.html')


@app.route('/qhcb')
def qhcb():
    return render_template('pricing.html')


@app.route('/geobim')
def geobim():
    return render_template('geobim.html')


@app.route('/quien')
def quien():
    return render_template('contact.html')


@app.route('/linea')
def linea():
    return render_template('linea.html')


@app.route('/visualizador')
def visualizador():
    return render_template('mapavisualizador.html')

@app.route('/editarinforme/<string:id>')
def editarinforme(id):
    doc_ref = db.collection(u'informes').document(id)
    doc = doc_ref.get()
    docdict = doc.to_dict()
    docdict["id"] = str(id)
    return render_template('editarinforme.html', informe=docdict), 302

@app.route('/informesociales')
def informesociales():
    return render_template('buscarinformedni.html')


@app.route('/gistablainfo')
def gistablainfo():
    return render_template('gistablainfo.html')


@app.route('/buscarinforme', methods=['GET', 'POST'])
def buscarinforme():
    if request.method == 'POST':
        jsonData = request.get_json()
        lista_de_dic = []
        if jsonData['operacion'] == 'buscardni':
            if jsonData['dni'] != '':
                docs = db.collection(u'informes').where(u'titulardni', u'==', jsonData['dni']).stream()
                for doc in docs:
                    docdict = doc.to_dict()
                    docdict["id"] = str(doc.id)
                    lista_de_dic.append(docdict)
                return jsonify(lista_de_dic)
            return jsonify("NODNI")

        elif jsonData['operacion'] == 'buscarinforme':
            return redirect(url_for('informe', id=str(jsonData['id'])), code=302)
        elif jsonData['operacion'] == 'editarinforme':
            return redirect(url_for('editarinforme', id=str(jsonData['id'])), code=302)
        elif jsonData['operacion'] == 'cargarconclusion':
            conclusion = {
                u'conclusionfin': str(jsonData['conclusion'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(conclusion)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme1':
            editar = {
                u'titular': str(jsonData['titular']),
                u'titulardni': str(jsonData['titulardni']),
                u'ocupante': str(jsonData['ocupante']),
                u'ocupantedni': str(jsonData['ocupantedni']),
                u'sitjur': str(jsonData['sitjur']),
                u'estadodeud': str(jsonData['estadodeud']),
                u'notdeud': str(jsonData['notdeud']),
                u'residedesde': str(jsonData['residedesde']),
                u'tipologia': str(jsonData['tipologia']),
                u'estado': str(jsonData['estado']),
                u'observacion': str(jsonData['observacion']),
                u'antecedenteiprodha': str(jsonData['antecedenteiprodha']),
                u'antecedenteviv': str(jsonData['antecedenteviv']),
                u'antecedentemv': str(jsonData['antecedentemv']),
                u'antecedentevr': str(jsonData['antecedentevr']),
                u'antecedentearreglo': str(jsonData['antecedentearreglo']),
                u'antecedentelote': str(jsonData['antecedentelote']),
                u'otrosinicio': str(jsonData['otrosinicio']),
                u'comoaccede': str(jsonData['comoaccede'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme2':
            editar = {
                u'titulardni': str(jsonData['titulardni']),
                u'dniconyuge': str(jsonData['dniconyuge']),
                u'dnihijos': str(jsonData['dnihijos']),
                u'actadematrimonio': str(jsonData['actadematrimonio']),
                u'unionconvivencial': str(jsonData['unionconvivencial']),
                u'escolaridad': str(jsonData['escolaridad']),
                u'estadociviltitular': str(jsonData['estadociviltitular']),
                u'estadocivilconyuge': str(jsonData['estadocivilconyuge']),
                u'correoelectronico': str(jsonData['correoelectronico']),
                u'observaciongrupo': str(jsonData['observaciongrupo'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme3':
            editar = {
                u'obrasocial': str(jsonData['obrasocial']),
                u'tienecud': str(jsonData['tienecud']),
                u'vigenciacud': str(jsonData['vigenciacud']),
                u'discapacidad': str(jsonData['discapacidad']),
                u'diagnostico': str(jsonData['diagnostico']),
                u'trasnsplantado': str(jsonData['trasnsplantado']),
                u'carnet': str(jsonData['carnet']),
                u'listadeespera': str(jsonData['listadeespera']),
                u'observaciontrasplante': str(jsonData['observaciontrasplante']),
                u'silladeruedas': str(jsonData['silladeruedas']),
                u'muletas': str(jsonData['muletas']),
                u'andador': str(jsonData['andador']),
                u'otrosmovilidad': str(jsonData['otrosmovilidad']),
                u'observaciongrupo': str(jsonData['observaciongrupo'])

            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme4':
            editar = {
                u'nombreingreso1': str(jsonData['nombreingreso1']),
                u'telefono1': str(jsonData['telefono1']),
                u'fechadelrecibo1': str(jsonData['fechadelrecibo1']),
                u'categorialaboral1': str(jsonData['categorialaboral1']),
                u'ingreso1': str(jsonData['ingreso1']),
                u'lugar1': str(jsonData['lugar1']),
                u'ocupacion1': str(jsonData['ocupacion1']),
                u'domicilio1': str(jsonData['domicilio1'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme5':
            editar = {
                u'nombreingreso2': str(jsonData['nombreingreso2']),
                u'telefono2': str(jsonData['telefono2']),
                u'fechadelrecibo2': str(jsonData['fechadelrecibo2']),
                u'categorialaboral2': str(jsonData['categorialaboral2']),
                u'ingreso2': str(jsonData['ingreso2']),
                u'lugar2': str(jsonData['lugar2']),
                u'ocupacion2': str(jsonData['ocupacion2']),
                u'domicilio2': str(jsonData['domicilio2'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme6':
            editar = {
                u'nombreingreso3': str(jsonData['nombreingreso3']),
                u'telefono3': str(jsonData['telefono3']),
                u'fechadelrecibo3': str(jsonData['fechadelrecibo3']),
                u'categorialaboral3': str(jsonData['categorialaboral3']),
                u'ingreso3': str(jsonData['ingreso3']),
                u'lugar3': str(jsonData['lugar3']),
                u'ocupacion3': str(jsonData['ocupacion3']),
                u'domicilio3': str(jsonData['domicilio3'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme7':
            editar = {
                u'nombreingreso4': str(jsonData['nombreingreso4']),
                u'telefono4': str(jsonData['telefono4']),
                u'fechadelrecibo4': str(jsonData['fechadelrecibo4']),
                u'categorialaboral4': str(jsonData['categorialaboral4']),
                u'ingreso4': str(jsonData['ingreso4']),
                u'lugar4': str(jsonData['lugar4']),
                u'ocupacion4': str(jsonData['ocupacion4']),
                u'domicilio4': str(jsonData['domicilio4'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme8':
            editar = {
                u'principalpagador': str(jsonData['principalpagador']),
                u'catlaboralpagador': str(jsonData['catlaboralpagador']),
                u'garante': str(jsonData['garante']),
                u'catlaboralgarante': str(jsonData['catlaboralgarante']),
                u'declaracionjurada': str(jsonData['declaracionjurada']),
                u'ingresospagador': str(jsonData['ingresospagador']),
                u'dnigarante': str(jsonData['dnigarante']),
                u'ingresosgarante': str(jsonData['ingresosgarante'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme9':
            editar = {
                u'titularprestamos': str(jsonData['titularprestamos']),
                u'prestamomonto': str(jsonData['prestamomonto']),
                u'plazo': str(jsonData['plazo']),
                u'consumomensual': str(jsonData['consumomensual']),
                u'tarjetas': str(jsonData['tarjetas']),
                u'tipodetarjeta': str(jsonData['tipodetarjeta']),
                u'observacionessiteco': str(jsonData['observacionessiteco'])

            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme10':
            editar = {
                u'luz': str(jsonData['luz']),
                u'montoluz': str(jsonData['montoluz']),
                u'luzformal': str(jsonData['luzformal']),
                u'agua': str(jsonData['agua']),
                u'aguamonto': str(jsonData['aguamonto']),
                u'aguaformal': str(jsonData['aguaformal']),
                u'cable': str(jsonData['cable']),
                u'cablemonto': str(jsonData['cablemonto']),
                u'cableformal': str(jsonData['cableformal']),
                u'internet': str(jsonData['internet']),
                u'internetmonto': str(jsonData['internetmonto']),
                u'internetformal': str(jsonData['internetformal']),
                u'observacionesservicios': str(jsonData['observacionesservicios'])
            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200
        elif jsonData['operacion'] == 'editarinforme11':
            editar = {
                u'cuotasocial': str(jsonData['cuotasocial']),
                u'cuotaprovisoria': str(jsonData['cuotaprovisoria']),
                u'cuotaestandar': str(jsonData['cuotaestandar']),
                u'planventa': str(jsonData['planventa']),
                u'planalquiler': str(jsonData['planalquiler']),
                u'otrosmodalidad': str(jsonData['otrosmodalidad']),
                u'plazopresentacion': str(jsonData['plazopresentacion']),
                u'observacionesplazo': str(jsonData['observacionesplazo'])

            }
            db.collection(u'informes').document(str(jsonData['id'])).update(editar)
            return '', 200


@app.route('/informe/<string:id>')
def informe(id):
    doc_ref = db.collection(u'informes').document(id)
    doc = doc_ref.get()
    docdict = doc.to_dict()
    docdict["id"] = str(id)
    return render_template('informe.html', informe=docdict), 302


@app.route('/lotesig2')
def lotesig2():
    gc = gspread.service_account(filename='static/credentials/service_account.json')

    sh = gc.open("ig2lotes")

    worksheet = sh.sheet1

    list_of_lists = worksheet.get_all_values()

    exel_list_d = []
    exel_list_n = []
    exel_list_p = []

    for i in range(1, len(list_of_lists)):
        if list_of_lists[i][1] == 'D':
            exel_list_d.append(list_of_lists[i])
        if list_of_lists[i][1] == 'N':
            exel_list_n.append(list_of_lists[i])
        if list_of_lists[i][1] == 'P':
            exel_list_p.append(list_of_lists[i])

    return render_template('ventalotes.html', exeld=json.dumps(exel_list_d), exeln=json.dumps(exel_list_n),
                           exelp=json.dumps(exel_list_p))


@app.route('/ventalotes')
def ventalotes():
    non_empty_estados = Estado.query.filter(Estado.estado != '').all()
    results = [{'id': row.id, 'estado': row.estado} for row in non_empty_estados]

    return render_template('ventalotes.html', estadolotes=json.dumps(results))


@app.route('/get_allidlotes', methods=['GET'])
def get_allidlotes():
    non_empty_estados = Estado.query.filter(Estado.estado != '').all()
    results = [{'id': row.id, 'estado': row.estado} for row in non_empty_estados]
    return jsonify(results)


@app.route('/get_ids_by_estados', methods=['POST'])
def get_ids_by_estados():
    data = request.get_json()
    if not data or 'estados' not in data:
        return jsonify({'error': 'Invalid request. Please provide an array of estados.'}), 400

    estados = data['estados']
    estados_str = [str(estado) for estado in estados]
    results = Estado.query.filter(Estado.estado.in_(estados_str)).all()
    ids = [str(result.id) for result in results]

    return jsonify({'ids': ids})


@app.route('/actualizarlotes', methods=['GET', 'POST', 'PUT'])
def actualizarlotes():
    if request.method == 'PUT':

        data = request.json
        estado_id = data['loteid']
        new_estado = data['estado']

        estado_row = Estado.query.get(estado_id)
        if estado_row is None:
            return jsonify({"message": f"Estado con id {estado_id} not found"}), 404

        estado_row.estado = new_estado
        dbsql.session.commit()

    return jsonify({"message": f"Estado con id {estado_id} actualizado", "dataid": estado_id, "dataestado": new_estado}), 201


@app.route('/mapavisitas')
def mapavisitas():
    return render_template('mapavisitas.html')


@app.route('/gisapp', methods=['POST', 'GET'])
def gisapp():
    if request.method == 'POST':
        linkm = request.form['linkm'].replace("https://i.imgur.com/", "")
        longlat = {'lat': request.form['lat'],
                   'linkm': linkm,
                   'obra': request.form['obra'],
                   'long': request.form['long']}

        print(longlat)
        return redirect(url_for('fotomap', longlat=longlat))

    return render_template('gisappindex.html')


@app.route('/arreglomicasa2')
def arreglomicasa2():
    gc = gspread.service_account(filename='static/credentials/service_account.json')
    pat = re.compile(r"^-?([1-8]?[1-9]|[1-9]0)\.{1}\d{1,6}")

    sh = gc.open("DB_arreglo_mi_casa")

    worksheet = sh.sheet1

    list_of_lists = worksheet.get_all_values()

    exel_list = []

    for i in range(1, len(list_of_lists)):
        if re.fullmatch(pat, list_of_lists[i][2]) and list_of_lists[i][2] != '':
            exel_list.append(list_of_lists[i])

    return render_template('arreglomicasa2.html', exel=json.dumps(exel_list))


@app.route('/fotomap/<string:longlat>')
def fotomap(longlat):
    return render_template('gisappfotomap.html', longlat=json.dumps(longlat))


@app.route('/gisappbrowser')
def gisappbrowser():
    return render_template('gisappbrowser.html')


@app.route('/encuesta1')
def encuestaRG01():
    return render_template('encuestarg01.html')


@app.route('/encuesta2')
def encuestaRG02():
    return render_template('encuestarg02.html')


@app.route('/encuesta3')
def encuestaRG03():
    return render_template('encuestarg03.html')


@app.route('/inscripcion')
def inscripcion():
    return render_template('inscripcion.html')


@app.route('/mapa')
def mapa():
    return render_template('mapagis.html')


@app.route('/')
def comunidadbim():
    return render_template('index.html')


@app.route('/menugis')
def menugis():
    return render_template('menugis.html')


@app.route('/testfetch')
def testfetch():
    return render_template('testfetch.html')


# Opening JSON file
f = open('static/geojson/jsongis.geojson', encoding='utf-8')

# returns JSON object as 
# a dictionary
data1 = json.load(f)


@app.route('/geojsongis')
def geojson():
    return data1

    # Opening JSON file


fileig2 = open('static/geojson/iglotes1y2.geojson', encoding='utf-8')

# returns JSON object as
# a dictionary
dataig2 = json.load(fileig2)


@app.route('/geojsonig2')
def geojson_ig2():
    return dataig2


y = open('static/geojson/exptes_pol.geojson', encoding='utf-8')

# returns JSON object as 
# a dictionary
data2 = json.load(y)


@app.route('/geojsonexptespol')
def geojson_exptespol():
    return data2


# Opening JSON file


h = open('static/geojson/exptes_pun.geojson', encoding='utf-8')

# returns JSON object as 
# a dictionary
data3 = json.load(h)


@app.route('/geojsonexptespun')
def geojson_exptespun():
    return data3

    # Opening JSON file


m = open('static/geojson/exptes_pun_buscar_obra.geojson', encoding='utf-8')

# returns JSON object as 
# a dictionary
data4 = json.load(m)


@app.route('/geojsonexptespunbuscar')
def geojson_exptespunbuscar():
    return data4


mz = open('static/geojson/visitas.geojson', encoding='utf-8')

# returns JSON object as 
# a dictionary
data5 = json.load(mz)


@app.route('/geojsonvisitas')
def geojson_visitas():
    return data5


# Wrap Flask app with Talisman
Talisman(app, content_security_policy=None)

if __name__ == '__main__':
    app.run(debug=True)

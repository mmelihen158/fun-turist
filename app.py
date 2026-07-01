import os
from flask import Flask, redirect, render_template_string, request, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "spremeni-to-skrivno-geslo")

# Na Renderju nastavi DATABASE_URL iz Render PostgreSQL.
# Lokalno, če DATABASE_URL ni nastavljen, uporablja SQLite datoteko local.db.
database_url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

DEJAVNOSTI = ["raft", "kajak", "sup", "transfer", "kanjon"]


class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ime = db.Column(db.String(120), unique=True, nullable=False)
    vnosi = db.relationship("Entry", backref="person", cascade="all, delete-orphan", lazy=True)


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    datum = db.Column(db.String(50), default="")
    dejavnost = db.Column(db.String(50), default="")
    fure = db.Column(db.Float, default=0)
    dodatno = db.Column(db.String(200), default="")
    denar = db.Column(db.Float, default=0)
    drug_vnos = db.Column(db.String(120), default="")
    drug_denar = db.Column(db.Float, default=0)
    izplacilo = db.Column(db.Float, default=0)


def to_float(value, default=0):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def to_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return default


def eur(value):
    value = to_float(value)
    if value.is_integer():
        return f"{int(value)} €"
    return f"{value:.2f} €"


def eur_or_empty(value):
    value = to_float(value)
    if value == 0:
        return ""
    return eur(value)


app.jinja_env.globals.update(eur=eur, eur_or_empty=eur_or_empty)


def get_person_or_redirect(person_id):
    return Person.query.get_or_404(person_id)


def skupni_denar(person):
    skupaj = 0
    for v in person.vnosi:
        skupaj += to_float(v.denar)
        skupaj -= to_float(v.izplacilo)
    return skupaj


def celoten_denar_brez_izplacil(person):
    return sum(to_float(v.denar) for v in person.vnosi)


def fure_po_dejavnosti(person):
    rezultat = {dejavnost: 0 for dejavnost in DEJAVNOSTI}
    for v in person.vnosi:
        if v.dejavnost in rezultat:
            rezultat[v.dejavnost] += to_float(v.fure)
    return rezultat


def shrani_vnos(person_id, datum="", dejavnost="", fure=0, dodatno="", denar=0, drug_vnos="", drug_denar=0, izplacilo=0):
    vnos = Entry(
        person_id=person_id,
        datum=datum,
        dejavnost=dejavnost,
        fure=fure,
        dodatno=dodatno,
        denar=denar,
        drug_vnos=drug_vnos,
        drug_denar=drug_denar,
        izplacilo=izplacilo,
    )
    db.session.add(vnos)
    db.session.commit()
    return vnos


BASE_HTML = """
<!doctype html>
<html lang="sl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            background: #f3f5f7;
            color: #1f2937;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 22px;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.08);
            margin-bottom: 18px;
        }
        h1, h2, h3 {
            margin-top: 0;
        }
        a {
            color: #0f766e;
            text-decoration: none;
            font-weight: bold;
        }
        .button, button {
            display: inline-block;
            border: none;
            border-radius: 12px;
            background: #0f766e;
            color: white;
            padding: 12px 16px;
            margin: 6px 4px;
            font-size: 16px;
            cursor: pointer;
            text-align: center;
        }
        .button.secondary, button.secondary {
            background: #374151;
        }
        .button.danger, button.danger {
            background: #b91c1c;
        }
        .button.light, button.light {
            background: #e5e7eb;
            color: #111827;
        }
        input {
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #cbd5e1;
            font-size: 16px;
            width: 100%;
            box-sizing: border-box;
            margin: 8px 0 14px;
        }
        label {
            font-weight: bold;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            overflow-x: auto;
        }
        th, td {
            border-bottom: 1px solid #e5e7eb;
            padding: 10px;
            text-align: left;
        }
        th {
            background: #f9fafb;
        }
        .flash {
            background: #ecfdf5;
            color: #065f46;
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 12px;
        }
        .money {
            font-size: 28px;
            font-weight: bold;
            margin: 14px 0;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 10px;
        }
        .row-actions {
            white-space: nowrap;
        }
        @media (max-width: 700px) {
            .container { padding: 12px; }
            table { font-size: 13px; }
            th, td { padding: 7px; }
            .button, button { width: 100%; box-sizing: border-box; }
        }
    </style>
</head>
<body>
<div class="container">
    {% with messages = get_flashed_messages() %}
        {% if messages %}
            {% for message in messages %}
                <div class="flash">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    {{ body|safe }}
</div>
</body>
</html>
"""


def page(title, body, **context):
    return render_template_string(BASE_HTML, title=title, body=render_template_string(body, **context))


@app.route("/")
def index():
    osebe = Person.query.order_by(Person.ime.asc()).all()
    body = """
    <div class="card">
        <h1>Seznam imen</h1>
        <form method="post" action="{{ url_for('dodaj_ime') }}">
            <label>Dodaj ime</label>
            <input name="ime" placeholder="Vnesi ime" required>
            <button type="submit">Dodaj ime</button>
        </form>
    </div>

    <div class="card">
        <h2>Imena</h2>
        {% if osebe %}
            <div class="grid">
                {% for oseba in osebe %}
                    <div class="card" style="box-shadow:none; border:1px solid #e5e7eb; margin:0;">
                        <h3>{{ oseba.ime }}</h3>
                        <a class="button" href="{{ url_for('oseba', person_id=oseba.id) }}">Odpri ime</a>
                        <form method="post" action="{{ url_for('izbrisi_ime', person_id=oseba.id) }}" onsubmit="return confirm('Ali res izbrišem {{ oseba.ime }} in vse njegove podatke?')">
                            <button class="danger" type="submit">Odstrani ime</button>
                        </form>
                    </div>
                {% endfor %}
            </div>
        {% else %}
            <p>Ni še dodanih imen.</p>
        {% endif %}
    </div>
    """
    return page("Raft aplikacija", body, osebe=osebe)


@app.route("/dodaj-ime", methods=["POST"])
def dodaj_ime():
    ime = request.form.get("ime", "").strip()
    if not ime:
        flash("Ime ne sme biti prazno.")
        return redirect(url_for("index"))

    if Person.query.filter_by(ime=ime).first():
        flash("To ime že obstaja.")
        return redirect(url_for("index"))

    db.session.add(Person(ime=ime))
    db.session.commit()
    flash("Ime je dodano.")
    return redirect(url_for("index"))


@app.route("/oseba/<int:person_id>/izbrisi", methods=["POST"])
def izbrisi_ime(person_id):
    person = get_person_or_redirect(person_id)
    db.session.delete(person)
    db.session.commit()
    flash("Ime in vsi njegovi podatki so izbrisani.")
    return redirect(url_for("index"))


@app.route("/oseba/<int:person_id>")
def oseba(person_id):
    person = get_person_or_redirect(person_id)
    body = """
    <div class="card">
        <a href="{{ url_for('index') }}">← Nazaj</a>
        <h1>{{ person.ime }}</h1>
        <a class="button" href="{{ url_for('vnos_podatkov', person_id=person.id) }}">Vnesi podatke</a>
        <a class="button secondary" href="{{ url_for('fure', person_id=person.id) }}">Fure</a>
        <a class="button secondary" href="{{ url_for('celoten_seznam', person_id=person.id) }}">Celoten seznam</a>
        <a class="button secondary" href="{{ url_for('drug_vnos', person_id=person.id) }}">Drug vnos</a>

        <div class="money">Denar: {{ eur(skupaj) }}</div>

        <a class="button danger" href="{{ url_for('izplacaj', person_id=person.id) }}">Izplačaj</a>
    </div>
    """
    return page(person.ime, body, person=person, skupaj=skupni_denar(person))


@app.route("/oseba/<int:person_id>/vnos")
def vnos_podatkov(person_id):
    person = get_person_or_redirect(person_id)
    body = """
    <div class="card">
        <a href="{{ url_for('oseba', person_id=person.id) }}">← Nazaj</a>
        <h1>Vnesi podatke za {{ person.ime }}</h1>
        <form method="post" action="{{ url_for('izberi_dejavnost', person_id=person.id) }}">
            <label>Datum</label>
            <input type="date" name="datum" required>

            <h2>Izberi dejavnost</h2>
            <button type="submit" name="dejavnost" value="raft">Raft</button>
            <button type="submit" name="dejavnost" value="kajak">Kajak</button>
            <button type="submit" name="dejavnost" value="sup">Sup</button>
            <button type="submit" name="dejavnost" value="transfer">Transfer</button>
            <button type="submit" name="dejavnost" value="kanjon">Kanjon</button>
        </form>
    </div>
    """
    return page("Vnesi podatke", body, person=person)


@app.route("/oseba/<int:person_id>/vnos/izberi", methods=["POST"])
def izberi_dejavnost(person_id):
    person = get_person_or_redirect(person_id)
    datum = request.form.get("datum", "").strip()
    dejavnost = request.form.get("dejavnost", "").strip()

    if not datum or dejavnost not in DEJAVNOSTI:
        flash("Manjka datum ali dejavnost.")
        return redirect(url_for("vnos_podatkov", person_id=person.id))

    body = """
    <div class="card">
        <a href="{{ url_for('vnos_podatkov', person_id=person.id) }}">← Nazaj</a>
        <h1>{{ dejavnost|capitalize }} za {{ person.ime }}</h1>

        <form method="post" action="{{ url_for('shrani_podatke', person_id=person.id) }}">
            <input type="hidden" name="datum" value="{{ datum }}">
            <input type="hidden" name="dejavnost" value="{{ dejavnost }}">

            <label>Število fur</label>
            <input type="number" name="fure" min="1" step="1" required>

            {% if dejavnost in ['kanjon', 'kajak'] %}
                <label>Število ljudi</label>
                <input type="number" name="ljudje" min="1" step="1" required>
            {% endif %}

            {% if dejavnost == 'raft' %}
                <h2>Neopreni</h2>
                <button type="submit" name="neopreni" value="da">Da</button>
                <button type="submit" name="neopreni" value="ne">Ne</button>
            {% elif dejavnost == 'kajak' %}
                <h2>Neopreni</h2>
                <button type="submit" name="neopreni" value="da">Da</button>
                <button type="submit" name="neopreni" value="ne">Ne</button>
            {% elif dejavnost == 'transfer' %}
                <h2>Transfer</h2>
                <button type="submit" name="opcija" value="svoj kombi">Svoj kombi</button>
                <button type="submit" name="opcija" value="ne svoj kombi">Ne svoj kombi</button>
            {% else %}
                <button type="submit">Shrani</button>
            {% endif %}
        </form>
    </div>
    """
    return page("Podatki", body, person=person, datum=datum, dejavnost=dejavnost)


@app.route("/oseba/<int:person_id>/vnos/shrani", methods=["POST"])
def shrani_podatke(person_id):
    person = get_person_or_redirect(person_id)
    datum = request.form.get("datum", "").strip()
    dejavnost = request.form.get("dejavnost", "").strip()
    fure = to_int(request.form.get("fure"), 0)

    if not datum or dejavnost not in DEJAVNOSTI or fure <= 0:
        flash("Podatki niso pravilni.")
        return redirect(url_for("vnos_podatkov", person_id=person.id))

    dodatno = ""
    denar = 0

    if dejavnost == "raft":
        denar = fure * 50
        neopreni = request.form.get("neopreni", "ne")
        if neopreni == "da":
            denar += 5
        dodatno = f"neopreni: {neopreni}"

    elif dejavnost == "sup":
        denar = fure * 45

    elif dejavnost == "kanjon":
        ljudje = to_int(request.form.get("ljudje"), 0)
        if ljudje <= 0:
            flash("Vnesi pravilno število ljudi.")
            return redirect(url_for("vnos_podatkov", person_id=person.id))
        dodatno = f"ljudi: {ljudje}"
        denar = ljudje * 5 + 50

    elif dejavnost == "kajak":
        ljudje = to_int(request.form.get("ljudje"), 0)
        if ljudje <= 0:
            flash("Vnesi pravilno število ljudi.")
            return redirect(url_for("vnos_podatkov", person_id=person.id))
        denar = ljudje * 5 + 45
        neopreni = request.form.get("neopreni", "ne")
        if neopreni == "da":
            denar += 5
        dodatno = f"ljudi: {ljudje}, neopreni: {neopreni}"

    elif dejavnost == "transfer":
        opcija = request.form.get("opcija", "")
        if opcija == "svoj kombi":
            denar = fure * 30
        elif opcija == "ne svoj kombi":
            denar = fure * 20
        else:
            flash("Izberi opcijo transferja.")
            return redirect(url_for("vnos_podatkov", person_id=person.id))
        dodatno = opcija

    shrani_vnos(person.id, datum=datum, dejavnost=dejavnost, fure=fure, dodatno=dodatno, denar=denar)
    flash(f"Vnos je shranjen. Izračun: {eur(denar)}")
    return redirect(url_for("oseba", person_id=person.id))


@app.route("/oseba/<int:person_id>/drug-vnos", methods=["GET", "POST"])
def drug_vnos(person_id):
    person = get_person_or_redirect(person_id)

    if request.method == "POST":
        dejavnost = request.form.get("dejavnost", "").strip()
        denar = to_float(request.form.get("denar"), -1)

        if not dejavnost or denar < 0:
            flash("Vnesi pravilno dejavnost in denar.")
            return redirect(url_for("drug_vnos", person_id=person.id))

        shrani_vnos(person.id, denar=denar, drug_vnos=dejavnost, drug_denar=denar)
        flash(f"Drug vnos je shranjen. Dodano: {eur(denar)}")
        return redirect(url_for("oseba", person_id=person.id))

    body = """
    <div class="card">
        <a href="{{ url_for('oseba', person_id=person.id) }}">← Nazaj</a>
        <h1>Drug vnos za {{ person.ime }}</h1>
        <form method="post">
            <label>Dejavnost</label>
            <input name="dejavnost" placeholder="Npr. čiščenje, pomoč, ..." required>

            <label>Denar</label>
            <input type="number" name="denar" min="0" step="0.01" required>

            <button type="submit">Shrani</button>
        </form>
    </div>
    """
    return page("Drug vnos", body, person=person)


@app.route("/oseba/<int:person_id>/izplacaj", methods=["GET", "POST"])
def izplacaj(person_id):
    person = get_person_or_redirect(person_id)

    if request.method == "POST":
        datum = request.form.get("datum", "").strip()
        vsota = to_float(request.form.get("vsota"), -1)

        if not datum or vsota < 0:
            flash("Vnesi pravilen datum in vsoto.")
            return redirect(url_for("izplacaj", person_id=person.id))

        shrani_vnos(person.id, datum=datum, izplacilo=vsota)
        flash(f"Izplačilo je shranjeno. Odšteto: {eur(vsota)}")
        return redirect(url_for("oseba", person_id=person.id))

    body = """
    <div class="card">
        <a href="{{ url_for('oseba', person_id=person.id) }}">← Nazaj</a>
        <h1>Izplačaj {{ person.ime }}</h1>
        <form method="post">
            <label>Datum izplačila</label>
            <input type="date" name="datum" required>

            <label>Vsota izplačila</label>
            <input type="number" name="vsota" min="0" step="0.01" required>

            <button class="danger" type="submit">Izplačaj</button>
        </form>
    </div>
    """
    return page("Izplačaj", body, person=person)


@app.route("/oseba/<int:person_id>/fure")
def fure(person_id):
    person = get_person_or_redirect(person_id)
    fure_data = fure_po_dejavnosti(person)
    bruto = celoten_denar_brez_izplacil(person)
    body = """
    <div class="card">
        <a href="{{ url_for('oseba', person_id=person.id) }}">← Nazaj</a>
        <h1>Fure za {{ person.ime }}</h1>
        <h2>Raft: {{ fure_data['raft']|int }}</h2>
        <h2>Kajak: {{ fure_data['kajak']|int }}</h2>
        <h2>Sup: {{ fure_data['sup']|int }}</h2>
        <h2>Transfer: {{ fure_data['transfer']|int }}</h2>
        <h2>Kanjon: {{ fure_data['kanjon']|int }}</h2>
        <hr>
        <h2>Celoten denar: {{ eur(bruto) }}</h2>
        <p>To je vsota zaslužka brez odštevanja izplačil.</p>
    </div>
    """
    return page("Fure", body, person=person, fure_data=fure_data, bruto=bruto)


@app.route("/oseba/<int:person_id>/seznam")
def celoten_seznam(person_id):
    person = get_person_or_redirect(person_id)
    vnosi = Entry.query.filter_by(person_id=person.id).order_by(Entry.id.desc()).all()
    body = """
    <div class="card">
        <a href="{{ url_for('oseba', person_id=person.id) }}">← Nazaj</a>
        <h1>Celoten seznam za {{ person.ime }}</h1>
        <h2>Skupaj: {{ eur(skupaj) }}</h2>
        <div style="overflow-x:auto;">
            <table>
                <thead>
                    <tr>
                        <th>Datum</th>
                        <th>Dejavnost</th>
                        <th>Fure</th>
                        <th>Dodatno</th>
                        <th>Denar</th>
                        <th>Drug vnos</th>
                        <th>Drug denar</th>
                        <th>Izplačilo</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {% for v in vnosi %}
                        <tr>
                            <td>{{ v.datum }}</td>
                            <td>{{ v.dejavnost }}</td>
                            <td>{% if v.fure %}{{ v.fure|int }}{% endif %}</td>
                            <td>{{ v.dodatno }}</td>
                            <td>{{ eur_or_empty(v.denar) }}</td>
                            <td>{{ v.drug_vnos }}</td>
                            <td>{{ eur_or_empty(v.drug_denar) }}</td>
                            <td>{{ eur_or_empty(v.izplacilo) }}</td>
                            <td class="row-actions">
                                <form method="post" action="{{ url_for('izbrisi_vnos', entry_id=v.id) }}" onsubmit="return confirm('Ali res izbrišem to vrstico?')">
                                    <button class="danger" type="submit">Izbriši</button>
                                </form>
                            </td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    """
    return page("Celoten seznam", body, person=person, vnosi=vnosi, skupaj=skupni_denar(person))


@app.route("/vnos/<int:entry_id>/izbrisi", methods=["POST"])
def izbrisi_vnos(entry_id):
    vnos = Entry.query.get_or_404(entry_id)
    person_id = vnos.person_id
    db.session.delete(vnos)
    db.session.commit()
    flash("Vrstica je izbrisana.")
    return redirect(url_for("celoten_seznam", person_id=person_id))


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)

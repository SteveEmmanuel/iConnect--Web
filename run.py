from app import app, db, bcrypt, login_manager
import flask
from flask import render_template, request, url_for, redirect, json
from app import User, Customers, CustomersGrantedEntry, get_approved_customers,\
    check_admit_eligiblity, get_unapproved_customers, get_all_customers
from sqlalchemy import or_
from datetime import datetime
import flask_admin
from flask_admin.contrib.sqla import ModelView
from Forms import LoginForm
from flask_login import login_user, logout_user, current_user
from pyfcm import FCMNotification

'''import logging
logging.basicConfig(
    filename="/home/steveisredatw/tasks.log",
    level=logging.DEBUG
)
logging.info("At the starting line")'''


class LoginRequiredModelView(ModelView):

    def is_accessible(self):
        return current_user.is_authenticated


# set optional bootswatch theme
app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

admin = flask_admin.Admin(app, name='Admin')
admin.add_view(LoginRequiredModelView(Customers, db.session))
admin.add_view(LoginRequiredModelView(User, db.session))
admin.add_view(LoginRequiredModelView(CustomersGrantedEntry, db.session))


@app.route('/')
@app.route('/home')
def home():
    return render_template('index.html')


@app.route('/page', methods=['GET', 'POST'])
def paginate():
    search_value = request.form['search[value]']

    query = db.session.query(Customers)
    total_count = query.count()

    if 'date' in request.form:
        if request.form['date'].__len__() != 0:
            date = datetime.strptime(request.form['date'], '%d/%m/%Y')
            query = query.filter(Customers.date == date.date())

    if search_value.__len__() != 0:
        query = query.filter(or_(Customers.name.contains(search_value),
                                 Customers.series.contains(search_value)))
    filtered_count = query.count()

    if request.form['order[0][column]'] == '0':
        order_column = Customers.name
    if request.form['order[0][column]'] == '1':
        order_column = Customers.email
    if request.form['order[0][column]'] == '2':
        order_column = Customers.phone_number
    if request.form['order[0][column]'] == '3':
        order_column = Customers.date
    if request.form['order[0][column]'] == '4':
        order_column = Customers.time

    if request.form['order[0][dir]'] == 'asc':
        order_column = order_column.asc()
    else:
        order_column = order_column.desc()

    query = query.order_by(order_column)

    length = int(request.form['length'])
    start = int(request.form['start'])
    query = query.paginate(page=(start / length) + 1, per_page=length, error_out=False, max_per_page=None)
    # print request.form
    result_dict = []
    for q in query.items:
        result_dict.append([q.name, q.email, q.phone_number, q.date.strftime('%a, %d/%m/%Y'), q.time.strftime('%H:%M')])
    data = {'draw': int(request.form['draw']),
            'recordsTotal': total_count,
            'recordsFiltered': filtered_count,
            'data': result_dict}

    return flask.jsonify(data)


@login_manager.user_loader
def user_loader(user_id):
    """Given *user_id*, return the associated User object.

    :param unicode user_id: user_id (email) user to retrieve

    """
    return db.session.query(User).filter(User.id.__eq__(user_id)).first()


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter(User.user_id.__eq__(form.user_id.data))
        if user.count() == 1:
            user = user.first()
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for("admin.index"))
    return render_template("login.html", form=form)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def processing_error(error):
    return render_template('500.html', error=error), 500


# endpoint to create new customer
@app.route("/customer", methods=["POST"])
def add_customer():
    name = request.json['name']
    email = request.json['email']
    phone_number = request.json['phone_number']
    firebase_token = request.json['firebase_token']
    now = datetime.now()
    date = now.date()
    time = now.time()

    new_customer = Customers(name, phone_number, email, date, time, firebase_token)

    db.session.add(new_customer)
    try:
        db.session.commit()
    except:
        return json.dumps({"error": "error"}), 500

    result_dict = {"name": new_customer.name, "email": new_customer.email, "phone_number": new_customer.phone_number,
                   "date": new_customer.date.strftime('%a, %d/%m/%Y'), "time": new_customer.time.strftime('%H:%M'),
                   "firebase_token": new_customer.firebase_token}
    return json.dumps(result_dict)


# endpoint to get customer details
@app.route("/checkapproval", methods=["POST"])
def check_approval():
    firebase_token = request.json['firebase_token']

    customer_query = db.session.query(Customers).filter_by(firebase_token=firebase_token)


    if customer_query.count() > 0:
        customer = customer_query.first()
        customer_granted_query = db.session.query(CustomersGrantedEntry).filter_by(
            customer_id=customer_query.first().id)

        if customer_granted_query.count() > 0:
            result_dict = {"error": "Customer already admitted"}

        elif customer.approved is True:
            result_dict = {"name": customer.name, "email": customer.email, "phone_number": customer.phone_number,
                           "date": customer.date.strftime('%a, %d/%m/%Y'), "time": customer.time.strftime('%H:%M'),
                           "firebase_token": customer.firebase_token}
        else:
            result_dict = {"error": "customer not approved"}
    else:
        result_dict = {"error": "no customer by that id"}

    return json.dumps(result_dict)


# endpoint to grant approval to customer
@app.route("/grantapproval", methods=["POST"])
def grant_approval():
    firebase_token = request.json['firebase_token']

    query = db.session.query(Customers).filter_by(firebase_token=firebase_token)

    if query.count() > 0:
        customer = query.first()
        customer.grant_customer_approval()
        db.session.commit()
        result_dict = {"success": "customer granted approval"}
    else:
        result_dict = {"error": "no customer by that id"}
    push_service = FCMNotification(
        api_key="AAAAVb7FMzM:APA91bEvhiscqN1aIUePPKSFcUaB-zLwGjle5Idt67F7VPiXzVtPiTQ70r9RmsbFxi14sHVKCnDsZxD-KI0qv2CMP8Kid7wCuSVqR7ZmnshMF2IIFGp6pnwVJD4br6XvWmwsdrhW68yq")

    registration_id = firebase_token
    message_body = "Registration Approved. Click to view entry pass."
    data_message = {
        "Nick": "Mario",
        "body": "great match!",
        "Room": "PortugalVSDenmark"
    }
    result = push_service.notify_single_device(registration_id=registration_id, message_body=message_body,
                                               data_message=data_message)
    return json.dumps(result_dict)


# endpoint to reject approval to customer
@app.route("/rejectapproval", methods=["POST"])
def reject_approval():
    firebase_token = request.json['firebase_token']

    query = db.session.query(Customers).filter_by(firebase_token=firebase_token)

    if query.count() > 0:
        customer = query.first()
        customer.reject_customer_approval()
        db.session.commit()
        result_dict = {"success": "customer rejected approval"}
    else:
        result_dict = {"error": "no customer by that id"}
    return json.dumps(result_dict)


# endpoint to create new customer
@app.route("/getadmiteligiblecustomerlist", methods=["GET"])
def get_admit_eligible_customer_list():

    customers = get_approved_customers()
    result_dict = []
    for customer in customers:
        if check_admit_eligiblity(customer) is False:
            result_dict.append({"name": customer.name, "email": customer.email, "phone_number": customer.phone_number,
                       "date": customer.date.strftime('%a, %d/%m/%Y'), "time": customer.time.strftime('%H:%M'),
                        "firebase_token": customer.firebase_token})

    return json.dumps(result_dict)


# endpoint to get approved customers list
@app.route("/approvedcustomers", methods=["GET"])
def get_approved_customer_list():

    customers = get_approved_customers()
    result_dict = []
    for customer in customers:
        result_dict.append({"name": customer.name, "email": customer.email, "phone_number": customer.phone_number,
                   "date": customer.date.strftime('%a, %d/%m/%Y'), "time": customer.time.strftime('%H:%M'),
                    "firebase_token": customer.firebase_token})

    return json.dumps(result_dict)


# endpoint to get unapproved customers list
@app.route("/unapprovedcustomers", methods=["GET"])
def get_unapproved_customer_list():

    customers = get_unapproved_customers()
    result_dict = []
    for customer in customers:
        result_dict.append({"name": customer.name, "email": customer.email, "phone_number": customer.phone_number,
                   "date": customer.date.strftime('%a, %d/%m/%Y'), "time": customer.time.strftime('%H:%M'),
                    "firebase_token": customer.firebase_token})

    return json.dumps(result_dict)


# endpoint to get all customers list
@app.route("/allcustomers", methods=["GET"])
def get_all_customer_list():

    customers = get_all_customers()
    result_dict = []
    for customer in customers:
        result_dict.append({"name": customer.name, "email": customer.email, "phone_number": customer.phone_number,
                   "date": customer.date.strftime('%a, %d/%m/%Y'), "time": customer.time.strftime('%H:%M'),
                    "firebase_token": customer.firebase_token})

    return json.dumps(result_dict)


# endpoint to admit customer
@app.route("/admit", methods=["POST"])
def admit_customer():
    firebase_token = request.json['firebase_token']

    now = datetime.now()
    date = now.date()
    time = now.time()

    customer_query = db.session.query(Customers).filter_by(firebase_token=firebase_token)

    if customer_query.count() > 0:
        customer_granted_query = db.session.query(CustomersGrantedEntry).filter_by(customer_id=customer_query.first().id)

        if customer_granted_query.count() > 0:
            result_dict = {"error": "Customer already admitted"}
        else:

            granted_customer = CustomersGrantedEntry()
            granted_customer.time = time
            granted_customer.date = date
            granted_customer.customer = customer_query.first()
            db.session.add(granted_customer)
            try:
                db.session.commit()
                result_dict = {"name": granted_customer.customer.name, "email": granted_customer.customer.email,
                               "phone_number": granted_customer.customer.phone_number,
                               "date": granted_customer.date.strftime('%a, %d/%m/%Y'),
                               "time": granted_customer.time.strftime('%H:%M')}
            except:
                return json.dumps({"error": "commit error"})

    return json.dumps(result_dict)


if __name__ == '__main__':
    port = 8080
    app.run(host='0.0.0.0', port=port)

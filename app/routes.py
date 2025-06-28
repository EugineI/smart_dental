from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from .forms import RegisterForm, LoginForm
from .models import User
from . import db
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from app import login_manager
from flask_mail import Message
from . import mail
from .forms import AppointmentForm
from .models import Appointment

main = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
def home():
    return render_template('home.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('main.login'))
    return render_template('register.html', form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            elif user.role == 'doctor':
                return redirect(url_for('main.doctor_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))
        else:
            flash('Invalid email or password.')
    return render_template('login.html', form=form)

@main.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('main.login'))


@main.route('/book', methods=['GET', 'POST'])
@login_required
def book():
    form = AppointmentForm()
    if form.validate_on_submit():
        appointment = Appointment(
            patient_id=current_user.id,
            date=form.date.data,
            time=form.time.data,
            reason=form.reason.data,
            status='Pending'
        )
        db.session.add(appointment)
        db.session.commit()
        flash('Appointment booked successfully!')
        return redirect(url_for('main.dashboard'))
    return render_template('book.html', form=form)

@main.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('main.dashboard'))

    # Get all appointments
    pending_appointments = Appointment.query.filter_by(status="Pending").order_by(Appointment.date, Appointment.time).all()
    approved_appointments = Appointment.query.filter_by(status="Approved").order_by(Appointment.date, Appointment.time).all()

    # Get all patients and doctors
    patients = User.query.filter_by(role='patient').all()
    doctors = User.query.filter_by(role='doctor').all()

    if request.method == 'POST':
        if 'add_doctor' in request.form:
            # Add new doctor
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')

            if User.query.filter_by(email=email).first():
                flash("Email already registered.")
            else:
                new_doc = User(
                    name=name,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role='doctor'
                )
                db.session.add(new_doc)
                db.session.commit()

            return redirect(url_for('main.admin_dashboard'))

        # Update appointment
        app_id = request.form.get('app_id')
        message = request.form.get('message')
        appointment = Appointment.query.get(app_id)

        if appointment:
            if appointment.status == "Pending":
                doctor_id = request.form.get('dentist')
                doctor = User.query.get(doctor_id)

                if doctor:
                    appointment.dentist = doctor.name
                    appointment.message = message
                    appointment.status = "Approved"

                    # Send email
                    
                    msg = Message(
                            subject="New Appointment Assigned",
                            sender=current_app.config['MAIL_USERNAME'],
                            recipients=[doctor.email],
                            body=f"""
                            Hi Dr. {doctor.name},
                            You have been assigned a new dental appointment.

                            Patient: {appointment.patient.name}
                            Date: {appointment.date}
                            Time: {appointment.time}
                            Reason: {appointment.reason}

                            Message from admin:
                            {message}
                            Please log in to your dashboard for more details.
                            Thank you.
                            """
                            )
                    mail.send(msg)
        
                else:
                    flash("Selected doctor not found.")
            elif appointment.status == "Approved":
                # Only update the message
                appointment.message = message
                flash(f"Message updated for appointment {app_id}.")
            else:
                flash("Unknown appointment status.")

            db.session.commit()
            return redirect(url_for('main.admin_dashboard'))

    return render_template(
        'admin.html',
        pending_appointments=pending_appointments,
        approved_appointments=approved_appointments,
        doctors=doctors,
        patients=patients
    )


@main.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'patient':
        return redirect(url_for('main.admin_dashboard'))
    appointments = Appointment.query.filter_by(patient_id=current_user.id).all()
    return render_template('dashboard.html', appointments=appointments, name=current_user.name)

@main.route('/doctor', methods=['GET'])
@login_required
def doctor_dashboard():
    if current_user.role != 'doctor':
        return redirect(url_for('main.dashboard'))

    # Get appointments assigned to this doctor
    appointments = Appointment.query.filter_by(dentist=current_user.name).order_by(Appointment.date, Appointment.time).all()

    return render_template('doctor_dashboard.html', appointments=appointments)

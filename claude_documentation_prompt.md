# Claude Prompt — Mike J Spa Project Documentation

---

You are a senior software engineer and technical writer. I need you to produce a complete
set of software-engineering documentation artefacts for a web application called
**Mike J Spa — Luxury Wellness & Rejuvenation Booking System**.

Produce ALL of the following sections in one response, in order:

1. User Stories
2. Use Case Diagram (PlantUML) + Description
3. Sequence Diagrams (PlantUML) + Descriptions  
4. Class Diagram (PlantUML) + Description

Use **PlantUML syntax** for every diagram so the diagrams can be rendered immediately.
Write clear, professional descriptions for every artefact.

---

## SYSTEM CONTEXT

### What the system is
Mike J Spa is a full-stack Django + REST API + Single-Page-Application web system
for a luxury spa business. Customers book treatments online, staff manage their
schedules, and admins control the whole operation through a dedicated portal.

### Technology Stack
- **Backend**: Django 4, Django REST Framework, SQLite (dev) / PostgreSQL (prod)
- **Frontend**: Single HTML file with vanilla JS, Bootstrap 5, AOS animations
- **Auth**: Django session-based authentication (register / login / logout)
- **Email**: Django email backend (confirmation, cancellation, reschedule emails)
- **Deployment**: Render (whitenoise static files)

---

## DATA MODELS (Django Models)

### Service
- id, name, description, duration_minutes, price (Decimal)
- category: MASSAGE | FACIAL | BODY | NAILS | WELLNESS
- emoji (display icon), is_active, created_at

### Therapist
- id, name, bio
- user (OneToOne → Django User, optional — for staff login)
- specialties (ManyToMany → Service)
- working_days (comma-separated weekday numbers e.g. "1,2,3,4,5,6")
- working_hours_start, working_hours_end (TimeField)
- is_active, created_at

### Appointment
- id, confirmation_code (auto e.g. "SPA-A3F9K", unique)
- user (ForeignKey → User, nullable — guest bookings allowed)
- customer_name, customer_email, customer_phone, notes
- service (ForeignKey → Service)
- therapist (ForeignKey → Therapist)
- date (DateField), time_slot (TimeField)
- status: PENDING | CONFIRMED | CANCELLED | COMPLETED
- payment_status: UNPAID | PAID
- payment_method (CharField)
- created_at, updated_at
- Unique constraint: (therapist, date, time_slot)

### BlockedDate
- id, date (unique), reason, created_at

### Review
- id, customer_name, rating (1–5), comment, created_at

### Django User (built-in, extended by role)
- is_superuser / is_staff → Admin role
- has therapist_profile (reverse OneToOne) → Staff role
- otherwise → Customer role

---

## API ENDPOINTS (Django REST Framework)

### Auth
- POST /spa/api/auth/register/   → Register new customer
- POST /spa/api/auth/login/      → Login (customer / staff / admin)
- POST /spa/api/auth/logout/     → Logout
- GET  /spa/api/auth/me/         → Get current authenticated user & role

### Services
- GET  /spa/api/services/        → List all active services
- POST /spa/api/services/        → Create service (admin only, X-Admin-Password header)

### Therapists
- GET  /spa/api/therapists/      → List therapists (filter by ?service=id)

### Availability
- GET  /spa/api/availability/?therapist=id&date=YYYY-MM-DD → Available time slots

### Appointments
- POST  /spa/api/appointments/                    → Create booking (auth required)
- GET   /spa/api/appointments/history/            → List bookings by logged-in user or ?email=
- GET   /spa/api/appointments/<code>/             → Get single appointment
- PATCH /spa/api/appointments/<code>/cancel/      → Cancel (24h policy)
- POST  /spa/api/appointments/<code>/reschedule/  → Reschedule (24h policy)
- POST  /spa/api/appointments/<code>/pay/         → Mark as paid (demo)

### Staff
- PATCH /spa/api/staff/availability/              → Update own working hours/days (staff only)

### Admin (X-Admin-Password: 77510438 header required)
- GET   /spa/api/admin/appointments/              → List all appointments (filter by ?status=)
- PATCH /spa/api/admin/appointments/<id>/status/  → Update appointment status
- GET   /spa/api/admin/blocked-dates/             → List blocked dates
- POST  /spa/api/admin/blocked-dates/             → Add blocked date / holiday
- DELETE /spa/api/admin/blocked-dates/<id>/       → Remove blocked date
- PUT   /spa/api/admin/services/<id>/             → Edit a service
- DELETE /spa/api/admin/services/<id>/            → Deactivate a service
- GET   /spa/api/admin/users/                     → List all user accounts
- POST  /spa/api/admin/users/                     → Create user account (customer/staff/admin)
- GET   /spa/api/admin/reports/                   → Analytics: revenue, booking metrics, popular services

### Reviews
- GET  /spa/api/reviews/   → List recent reviews
- POST /spa/api/reviews/   → Submit a review

### Frontend Pages
- GET /spa/              → Main customer SPA (index.html)
- GET /spa/staff-portal/ → Staff portal HTML
- GET /spa/admin-portal/ → Admin portal HTML

---

## KEY BUSINESS RULES

1. The spa is **closed on Sundays** — no bookings can be made for Sundays.
2. **BlockedDates** (holidays/special events) prevent booking on specific dates.
3. Therapists only offer services listed in their **specialties**; the system validates this.
4. **Double-booking prevention**: a therapist cannot have two overlapping appointments (unique_together constraint).
5. **Cancellation policy**: appointments can only be cancelled at least **24 hours** in advance.
6. **Rescheduling policy**: appointments can only be rescheduled at least **24 hours** in advance.
7. A confirmed appointment triggers an **email notification** to the customer.
8. Cancellations and reschedules also trigger **email notifications**.
9. Customers must be **logged in** to make a booking (auth gate enforced on frontend).
10. Guests can still look up bookings by email on the "My Bookings" page.
11. Package pricing is **frontend-calculated** (Standard = base price, Premium = ×1.5, VIP = ×2.5).
12. Payment is **demo/simulated** — no real payment gateway is integrated.
13. Admin role is determined by `is_staff` or `is_superuser` flags on the Django User.
14. Staff role is determined by the existence of a linked `therapist_profile`.
15. Availability slots are **60-minute** intervals between therapist working hours.

---

## USER ROLES

### Customer
- Browse treatments (services) and gallery
- Register / login / logout
- View service details and choose Standard / Premium / VIP package
- Go through 5-step booking wizard: Experience → Therapist → Time Slot → Details → Payment
- Receive email confirmation
- View their bookings (My Bookings section)
- Cancel or reschedule their own bookings
- Submit star-rating reviews
- Print/view receipt after booking

### Staff (Therapist)
- Login via staff portal (/spa/staff-portal/)
- View their own assigned appointments
- Update their working hours and working days
- Mark appointments as Completed

### Admin
- Login via admin portal (/spa/admin-portal/)
- View and filter all appointments
- Approve / Confirm / Complete / Cancel any appointment
- Manage services (create, edit, deactivate)
- Manage therapists and user accounts
- Block dates (holidays/special events)
- View revenue and booking analytics reports
- Create new user accounts (customer / staff / admin)

---

## INSTRUCTIONS FOR EACH SECTION

---

### SECTION 1 — USER STORIES

Write user stories in the format:
> **As a [role], I want to [action] so that [benefit].**

Group them by role: Customer, Staff (Therapist), Admin.
Write at least 6 user stories per role (18+ total).
For each story, also list 2–3 **acceptance criteria** as bullet points.

---

### SECTION 2 — USE CASE DIAGRAM

Draw a PlantUML use case diagram showing:
- All three actors: Customer, Staff, Admin (and the System as a fourth actor for automated emails)
- All major use cases grouped by actor
- Include/extend relationships where appropriate (e.g. "Book Appointment" includes "Login")
- Show the system boundary box labelled "Mike J Spa System"

After the diagram code block, write a **3–5 paragraph description** explaining:
- The actors and their goals
- The main use case groups
- The key include/extend relationships and why they exist

---

### SECTION 3 — SEQUENCE DIAGRAMS

Draw PlantUML sequence diagrams for the following 4 scenarios.
For each diagram write a **2–3 paragraph description** explaining the flow.

**Scenario A: Customer Books an Appointment (Happy Path)**
Participants: Browser (Customer), SPA Frontend (JS), Django Backend, Database, Email Service
Cover: auth check → service selection → package selection → wizard steps (therapist, date, slot, details, payment) → appointment creation → email sent → receipt shown.

**Scenario B: Admin Confirms an Appointment**
Participants: Browser (Admin), Admin Portal (JS), Django Backend, Database, Email Service
Cover: admin logs in → loads appointments → selects pending appointment → changes status to CONFIRMED → backend saves → email sent to customer.

**Scenario C: Customer Cancels a Booking**
Participants: Browser (Customer), SPA Frontend (JS), Django Backend, Database, Email Service
Cover: customer views bookings → clicks Cancel → 24h policy check → appointment cancelled → email sent → UI refreshed.

**Scenario D: Staff Updates Availability**
Participants: Browser (Staff), Staff Portal (JS), Django Backend, Database
Cover: staff logs in → views portal → updates working days/hours → backend updates therapist record → confirmation shown.

---

### SECTION 4 — CLASS DIAGRAM

Draw a PlantUML class diagram showing:
- All 5 domain model classes: Service, Therapist, Appointment, BlockedDate, Review
- The Django built-in User class (show only relevant fields: id, username, email, first_name, is_staff, is_superuser)
- All relationships with correct UML notation (association, aggregation, composition, multiplicity labels)
- Key attributes and methods for each class
- Include the AppointmentStatus and ServiceCategory enumerations
- Include the 3 DRF Serializer classes as «serializer» stereotyped classes and show which model they map to
- Include the key APIView classes as «view» stereotyped classes, grouped logically

After the diagram code block, write a **4–6 paragraph description** explaining:
- The core domain model and entity relationships
- The role of each model class
- How the serializers bridge the models and API
- How the view classes are organized
- The use of Django's built-in User model and how roles are derived
- Any design patterns used (e.g. template method in APIView, active record in Django ORM)

---

Format your entire response with clear `##` headings for each section and sub-headings for each diagram/scenario. Use fenced code blocks with `plantuml` language tag for all diagrams.

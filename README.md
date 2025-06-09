# 🧭 Travel Service Backend API (FastAPI + Mock JSON)

A mock backend travel management system built using **FastAPI**. Designed for educational, prototyping, and early-stage development purposes, this system operates entirely on local JSON files — no database required.

---

## 📁 Project Structure

```
travel_service_backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI app initialization
│   ├── models/             # Pydantic models
│   │   ├── customer.py     # Customer profile models
│   │   ├── destination.py
│   │   ├── booking.py
│   │   ├── schedule.py
│   │   ├── payment.py
│   │   ├── vehicle.py
│   │   ├── staff.py
│   │   ├── feedback.py
│   │
│   ├── routes/             # API routes
│   │   ├── __init__.py
│   │   ├── customers.py    # Customer profile endpoints
│   │   ├── destinations.py
│   │   ├── bookings.py
│   │   ├── schedules.py
│   │   ├── payments.py
│   │   ├── vehicles.py
│   │   ├── staff.py
│   │   ├── feedback.py
│   │
│   └── data/               # Mock data
│       ├── customers.json
│       ├── bookings.json
│       ├── destinations.json
│       ├── schedules.json
│       ├── payments.json
│       ├── vehicles.json
│       ├── staff.json
│       ├── feedback.json
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures
│   ├── test_customer_api.py  # Unit tests for customer endpoints
│   ├── test_destination_api.py
│   ├── test_booking_api.py
│   ├── test_schedule_api.py
│   ├── test_payment_api.py
│   ├── test_vehicle_api.py
│   ├── test_staff_api.py
│   ├── test_feedback_api.py
│   └── test_data/            # Test fixture data
│
├── requirements.txt          # Project dependencies
├── run_tests.py           # Run all of tests
└── README.md
```

---

## ⚙️ How to Run

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

2. **Run the API server**:

```bash
uvicorn app.main:app --reload
```

3. **Explore docs**:

* Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
* ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔍 Key Highlights

### ✅ CRUD APIs Implemented (Each from Separate Conversations)

| # | Entity      | Status      | Key Features                                                   |
| - | ----------- | ----------- | -------------------------------------------------------------- |
| 1 | Customer    | ✅ Completed | Soft delete, hard delete, cascade delete, update validations   |
| 2 | Destination | ✅ Completed | Search/filtering, pagination                                   |
| 3 | Booking     | ✅ Completed | Relational validation, cancellation logic                      |
| 4 | Schedule    | ✅ Completed | Time conflict prevention, availability toggling                |
| 5 | Payment     | ✅ Completed | Refund validation, payment method checking                     |
| 6 | Vehicle     | ✅ Completed | Bulk insert, soft/reactivation, filter by type and destination |
| 7 | Staff       | ✅ Completed | Role/destination validation, reactivation, summary stats       |
| 8 | Feedback    | ✅ Completed | Soft-delete, admin notes, status filtering                     |

---

## 🧪 Unit Test Results
⚙️ How to Run
Run all of tests using [run_tests.py](https://github.com/riku-k061/travel-backend/blob/main/run_tests.py) 

```bash
python run_tests.py 
```

📸 Screenshots:

| Description          | Link                                                                                          |
| -------------------- | --------------------------------------------------------------------------------------------- |
| ✅ Unit test result 1 | [View](https://drive.google.com/file/d/124hb2BF6CxIzBxKzcAs8c8RdarwYrifu/view?usp=drive_link) |
| ✅ Unit test result 2 | [View](https://drive.google.com/file/d/1jgJDvkiMBQJWsLQ2WDwTRjq7OGR4H405/view?usp=drive_link) |
| ✅ Unit test result 1 | [View](https://drive.google.com/file/d/1372gpy3erpJxuy2pKelKyLmTQKwCIwsu/view?usp=drive_link) |
| ✅ Unit test result 1 | [View](https://drive.google.com/file/d/1Gt8nPOX5DWE4tc03HFCJzpVnFheQNFtY/view?usp=drive_link) |

---

## 🚀 Code Execution Screenshots

| Description   | Link                                                                                          |
| ------------- | --------------------------------------------------------------------------------------------- |
| App running 1 | [View](https://drive.google.com/file/d/1UXcjBJBxMaM1VE_EFvjoP5T9-dScxwE-/view?usp=drive_link) |
| App running 2 | [View](https://drive.google.com/file/d/1lyFMQhh-m4H5LILV4TBy7wRhfLJYIFnl/view?usp=drive_link) |
| App running 3 | [View](https://drive.google.com/file/d/1p2i3jpHPAt57y52g-9bVK3LEeHUkHT4P/view?usp=drive_link) |
| App running 4 | [View](https://drive.google.com/file/d/1EUUHl2j7c1hD2RUbCSIHCG8VZh5NyuVw/view?usp=drive_link) |

---

## 📦 Dependencies

See [`requirements.txt`](./requirements.txt) for the full list.

---

## 📬 Feedback & Improvements

PRs and issues welcome — especially around:

* Improving test coverage
* Adding authentication
* Replacing JSON with a real database

---


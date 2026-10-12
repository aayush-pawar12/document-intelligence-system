"""Generate the sample documents used in the demo and tests.

Run once:  python samples/make_samples.py
Produces:  employees.csv, expenses.csv, products.xlsx, report.pdf
"""

import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def make_employees():
    rows = [
        ("E001", "Aarti Shah", "Mumbai", "Engineering", 92000, 29),
        ("E002", "Rahul Mehta", "Delhi", "Sales", 68000, 34),
        ("E003", "Priya Nair", "Mumbai", "Engineering", 105000, 31),
        ("E004", "Vikram Rao", "Bengaluru", "Marketing", 74000, 41),
        ("E005", "Sneha Iyer", "Mumbai", "Finance", 88000, 38),
        ("E006", "Arjun Das", "Delhi", "Engineering", 99000, 27),
        ("E007", "Kavya Menon", "Chennai", "Sales", 61000, 25),
        ("E008", "Rohit Gupta", "Bengaluru", "Finance", 115000, 45),
    ]
    df = pd.DataFrame(rows, columns=["EmpID", "Name", "City", "Department",
                                     "Salary", "Age"])
    df.to_csv(os.path.join(HERE, "employees.csv"), index=False)


def make_expenses():
    rows = [
        ("2026-01-05", "Office Rent", "Facilities", 45000),
        ("2026-01-09", "Laptops (x3)", "IT", 210000),
        ("2026-01-12", "Team Lunch", "HR", 4200),
        ("2026-01-18", "Cloud Hosting", "IT", 38000),
        ("2026-01-22", "Stationery", "Admin", 1800),
        ("2026-02-02", "Conference Tickets", "Marketing", 60000),
        ("2026-02-07", "Internet Bill", "Facilities", 5500),
        ("2026-02-14", "Software Licenses", "IT", 92000),
    ]
    df = pd.DataFrame(rows, columns=["Date", "Item", "Category", "Amount"])
    df.to_csv(os.path.join(HERE, "expenses.csv"), index=False)


def make_products():
    rows = [
        ("P01", "Wireless Mouse", "Accessories", 799, 120),
        ("P02", "Mechanical Keyboard", "Accessories", 3499, 0),
        ("P03", "27-inch Monitor", "Displays", 18999, 15),
        ("P04", "USB-C Hub", "Accessories", 2199, 0),
        ("P05", "Laptop Stand", "Accessories", 1299, 60),
        ("P06", "Webcam 1080p", "Peripherals", 2799, 8),
        ("P07", "Noise-cancel Headset", "Peripherals", 6999, 0),
    ]
    df = pd.DataFrame(rows, columns=["SKU", "Product", "Category",
                                     "Price", "Stock"])
    df.to_excel(os.path.join(HERE, "products.xlsx"), index=False)


def make_students():
    rows = [
        ("S01", "Isha Kulkarni", "Pune", 8.7, 20),
        ("S02", "Dev Patel", "Ahmedabad", 7.4, 21),
        ("S03", "Meera Joshi", "Pune", 9.1, 19),
        ("S04", "Karan Singh", "Jaipur", 6.8, 22),
        ("S05", "Nisha Reddy", "Hyderabad", 8.3, 20),
        ("S06", "Tanvi Bhat", "Pune", 9.5, 21),
    ]
    df = pd.DataFrame(rows, columns=["RollNo", "Name", "City", "GPA", "Age"])
    df.to_csv(os.path.join(HERE, "students.csv"), index=False)


def make_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(os.path.join(HERE, "report.pdf"), pagesize=A4)
    text = [
        ("Quarterly Operations Report", styles["Title"]),
        ("The engineering team shipped three major releases this quarter. "
         "Deployment frequency increased and the number of production incidents "
         "fell compared with the previous quarter.", styles["Normal"]),
        ("Hiring remained steady. The company added six engineers and two "
         "sales representatives. Attrition stayed low across all departments.",
         styles["Normal"]),
        ("Cloud infrastructure costs rose because of higher traffic, but the "
         "cost per request dropped after the caching migration. Overall margins "
         "improved for the quarter.", styles["Normal"]),
        ("Customer satisfaction scores improved for the third quarter in a row. "
         "Support response times were faster and the backlog shrank "
         "significantly.", styles["Normal"]),
    ]
    flow = []
    for content, style in text:
        flow.append(Paragraph(content, style))
        flow.append(Spacer(1, 12))
    doc.build(flow)


if __name__ == "__main__":
    make_employees()
    make_expenses()
    make_products()
    make_students()
    make_pdf()
    print("Samples written to", HERE)

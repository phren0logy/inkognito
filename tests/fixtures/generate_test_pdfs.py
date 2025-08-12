"""Generate test PDF files for integration testing."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from pathlib import Path


def create_simple_pdf(output_path: Path):
    """Create a simple PDF with text content."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Test Document")
    
    # Content
    c.setFont("Helvetica", 12)
    y_position = height - 1.5*inch
    
    content = [
        "This is a simple test document.",
        "It contains multiple lines of text.",
        "Perfect for testing PDF extraction."
    ]
    
    for line in content:
        c.drawString(1*inch, y_position, line)
        y_position -= 0.3*inch
    
    c.save()


def create_pii_pdf(output_path: Path):
    """Create a PDF containing PII for anonymization testing."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Employee Records")
    
    # Content with PII
    c.setFont("Helvetica", 12)
    y_position = height - 1.5*inch
    
    content = [
        "",
        "Employee Information:",
        "Name: Robert Smith",
        "Email: robert.smith@example.com",
        "Phone: (555) 123-4567",
        "SSN: 123-45-6789",
        "Date of Birth: January 15, 1980",
        "",
        "Emergency Contact:",
        "Name: Lisa Smith",
        "Phone: (555) 987-6543",
        "",
        "Manager: Jennifer Davis",
        "Email: jennifer.davis@example.com"
    ]
    
    for line in content:
        if y_position < 1*inch:
            c.showPage()
            y_position = height - 1*inch
            c.setFont("Helvetica", 12)
        
        if line.startswith(("Employee", "Emergency", "Manager")):
            c.setFont("Helvetica-Bold", 12)
        else:
            c.setFont("Helvetica", 12)
        
        c.drawString(1*inch, y_position, line)
        y_position -= 0.3*inch
    
    c.save()


def create_multipage_pdf(output_path: Path):
    """Create a multi-page PDF for segmentation testing."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    for chapter in range(1, 6):
        # Chapter title
        c.setFont("Helvetica-Bold", 18)
        c.drawString(1*inch, height - 1*inch, f"Chapter {chapter}")
        
        c.setFont("Helvetica-Bold", 14)
        c.drawString(1*inch, height - 1.5*inch, f"Introduction to Topic {chapter}")
        
        # Chapter content
        c.setFont("Helvetica", 12)
        y_position = height - 2*inch
        
        # Generate substantial content
        for paragraph in range(1, 11):
            if y_position < 2*inch:
                c.showPage()
                y_position = height - 1*inch
                c.setFont("Helvetica", 12)
            
            text = f"Paragraph {paragraph}: This chapter discusses important concepts "
            text += f"related to topic {chapter}. " * 3
            
            # Simple text wrapping
            words = text.split()
            line = ""
            for word in words:
                if len(line + word) > 70:
                    c.drawString(1*inch, y_position, line)
                    y_position -= 0.3*inch
                    line = word + " "
                else:
                    line += word + " "
            
            if line:
                c.drawString(1*inch, y_position, line)
                y_position -= 0.5*inch
        
        # New page for next chapter
        if chapter < 5:
            c.showPage()
    
    c.save()


def create_table_pdf(output_path: Path):
    """Create a PDF with table data."""
    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, "Sales Report Q4 2023")
    
    # Table headers
    c.setFont("Helvetica-Bold", 12)
    y_position = height - 2*inch
    
    headers = ["Date", "Customer", "Product", "Amount"]
    x_positions = [1*inch, 2.5*inch, 4.5*inch, 6.5*inch]
    
    for header, x_pos in zip(headers, x_positions):
        c.drawString(x_pos, y_position, header)
    
    y_position -= 0.3*inch
    c.line(1*inch, y_position, 7.5*inch, y_position)
    y_position -= 0.2*inch
    
    # Table data with some PII
    c.setFont("Helvetica", 11)
    data = [
        ["2023-10-15", "John Doe", "Widget A", "$1,234"],
        ["2023-10-16", "Jane Smith", "Widget B", "$2,345"],
        ["2023-10-17", "Bob Johnson", "Widget C", "$3,456"],
        ["2023-10-18", "Alice Brown", "Widget A", "$1,234"],
        ["2023-10-19", "Charlie Wilson", "Widget D", "$4,567"],
    ]
    
    for row in data:
        for value, x_pos in zip(row, x_positions):
            c.drawString(x_pos, y_position, value)
        y_position -= 0.3*inch
    
    # Summary
    y_position -= 0.5*inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, y_position, "Total Sales: $12,836")
    
    y_position -= 0.5*inch
    c.setFont("Helvetica", 12)
    c.drawString(1*inch, y_position, "Report prepared by: Sarah Miller")
    y_position -= 0.3*inch
    c.drawString(1*inch, y_position, "Email: sarah.miller@company.com")
    
    c.save()


if __name__ == "__main__":
    # Create test PDFs
    fixtures_dir = Path(__file__).parent
    
    print("Generating test PDFs...")
    
    create_simple_pdf(fixtures_dir / "simple.pdf")
    print("Created simple.pdf")
    
    create_pii_pdf(fixtures_dir / "employee_records.pdf")
    print("Created employee_records.pdf")
    
    create_multipage_pdf(fixtures_dir / "technical_manual.pdf")
    print("Created technical_manual.pdf")
    
    create_table_pdf(fixtures_dir / "sales_report.pdf")
    print("Created sales_report.pdf")
    
    print("\nAll test PDFs generated successfully!")
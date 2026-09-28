"""Prototype product catalogue for the deterministic adaptive intake engine.

These categories are illustrative prototype configurations, not insurer filings or
coverage terms.  All visibility and document rules are expressed using the
existing Question/Requirement rule engine.
"""

CATALOG = [
    {"name": "Personal Cyber Protection", "description": "Personal devices, online accounts and identity-protection risks.", "questions": [
        ("devices", "How many personal devices do you regularly use online?", "number", None),
        ("banking", "Do you use online banking or digital payment services?", "yesno", None),
        ("mfa", "Is multi-factor authentication enabled on your main email account?", "yesno", None),
        ("incident", "Have you experienced identity theft, account takeover, or cyber fraud in the past five years?", "yesno", None),
        ("incident_detail", "Please describe the previous cyber incident", "text", ("incident", "yes", None)),
    ], "requirements": [("Identity document", "Required to identify the person to be covered.", None), ("Cyber incident details", "Required because a previous cyber incident was reported.", ("incident", "yes"))]},
    {"name": "Personal Valuables & Marine", "description": "Personal valuables, collections and items carried or transported away from home.", "questions": [
        ("items", "What valuables or personal items need cover?", "text", None),
        ("value", "What is the approximate total value of the items?", "number", None),
        ("transport", "Will the items be carried or transported regularly?", "yesno", None),
        ("security", "How are the items normally stored or secured?", "text", None),
        ("losses", "Have there been losses, thefts, or damage claims in the past five years?", "yesno", None),
        ("loss_history", "Please describe the previous loss or claim", "text", ("losses", "yes", None)),
    ], "requirements": [("Valuable items list", "Required to identify the items to be covered.", None), ("Proof of value", "Required to support the value of the personal items.", None), ("Previous loss details", "Required because a previous loss or claim was reported.", ("losses", "yes"))]},
    {"name": "Personal Liability Protection", "description": "Personal third-party liability risks outside business activities.", "questions": [
        ("activities", "What regular personal activities could create third-party liability risk?", "text", None),
        ("pets", "Do you own or care for pets?", "yesno", None),
        ("watercraft", "Do you own or use personal watercraft?", "yesno", None),
        ("claims", "Have there been personal liability claims in the past five years?", "yesno", None),
        ("claim_history", "Please describe the previous personal liability claim", "text", ("claims", "yes", None)),
    ], "requirements": [("Personal activity summary", "Required to understand the personal liability exposure.", None), ("Previous claims details", "Required because a previous personal liability claim was reported.", ("claims", "yes"))]},
    {"name": "Motor Insurance", "description": "Private vehicles, drivers and road-use risks.", "questions": [
        ("vehicle_type", "What type of vehicle needs cover?", "select", (None, None, ["Car", "Motorcycle", "Van", "Other"])),
        ("vehicle_value", "What is the approximate vehicle value?", "number", None),
        ("vehicle_use", "How is the vehicle mainly used?", "select", (None, None, ["Personal use", "Commuting", "Business use", "Delivery"])),
        ("drivers", "How many regular drivers will use the vehicle?", "number", None),
        ("claims", "Have there been motor claims or accidents in the past five years?", "yesno", None),
        ("claim_history", "Please describe the previous motor claim or accident", "text", ("claims", "yes", None)),
    ], "requirements": [("Vehicle registration document", "Required to identify the vehicle to be insured.", None), ("Driving licence", "Required to verify the regular driver details.", None), ("Motor claims history", "Required because a previous motor claim or accident was reported.", ("claims", "yes"))]},
    {"name": "Home Insurance", "description": "Homes, personal belongings and residential property risks.", "questions": [
        ("home_type", "What type of home needs cover?", "select", (None, None, ["House", "Apartment", "Townhouse", "Other"])),
        ("occupancy", "Is the home owner-occupied, rented, or vacant?", "select", (None, None, ["Owner-occupied", "Rented", "Vacant"])),
        ("home_value", "What is the approximate rebuilding value?", "number", None),
        ("security", "What home security measures are in place?", "select", (None, None, ["Alarm", "Security cameras", "Locks only", "None"])),
        ("claims", "Have there been home or contents claims in the past five years?", "yesno", None),
        ("claim_history", "Please describe the previous home or contents claim", "text", ("claims", "yes", None)),
    ], "requirements": [("Proof of home ownership or tenancy", "Required to confirm the insured interest in the home.", None), ("Home valuation or rebuilding estimate", "Required to understand the value to be insured.", None), ("Home claims history", "Required because a previous home or contents claim was reported.", ("claims", "yes"))]},
    {"name": "Travel Insurance", "description": "Trips, travellers and overseas medical or travel disruption risks.", "questions": [
        ("destination", "What is the main travel destination?", "text", None),
        ("duration", "How many days will the trip last?", "number", None),
        ("travellers", "How many people are travelling?", "number", None),
        ("activities", "Will the trip include adventure or high-risk activities?", "yesno", None),
        ("medical", "Are there pre-existing medical conditions to declare?", "yesno", None),
        ("medical_detail", "Please describe the condition and any relevant treatment", "text", ("medical", "yes", None)),
    ], "requirements": [("Travel itinerary", "Required to confirm the destination and trip dates.", None), ("Traveller identification", "Required to identify the people to be covered.", None), ("Medical declaration", "Required because a pre-existing medical condition was declared.", ("medical", "yes"))]},
    {"name": "Construction Insurance", "description": "Construction projects, worksites and contractor risks.", "questions": [
        ("project_type", "What type of construction project is planned?", "text", None),
        ("project_value", "What is the approximate project value?", "number", None),
        ("duration", "How many months is the project expected to last?", "number", None),
        ("height_work", "Will work at height be carried out?", "yesno", None),
        ("subcontractors", "Will subcontractors be used?", "yesno", None),
        ("safety_detail", "Describe site safety controls for work at height", "text", ("height_work", "yes", None)),
    ], "requirements": [("Project contract or scope", "Required to understand the construction work being insured.", None), ("Project schedule", "Required to confirm the project duration and milestones.", None), ("Site safety plan", "Required because work at height is planned.", ("height_work", "yes"))]},
    {"name": "Marine Cargo Insurance", "description": "Goods in transit by sea, air, road or rail.", "questions": [
        ("goods", "What goods are being transported?", "text", None),
        ("cargo_value", "What is the approximate cargo value per shipment?", "number", None),
        ("routes", "Which shipping routes or destinations are used?", "text", None),
        ("mode", "Which transport modes are used?", "select", (None, None, ["Sea", "Air", "Road", "Rail", "Multiple modes"])),
        ("temperature", "Do the goods need temperature-controlled transport?", "yesno", None),
        ("losses", "Have there been cargo losses in the past five years?", "yesno", None),
        ("loss_history", "Please describe the previous cargo loss", "text", ("losses", "yes", None)),
    ], "requirements": [("Cargo or stock schedule", "Required to identify the goods in transit.", None), ("Shipping route information", "Required to understand transit exposure.", None), ("Cargo loss history", "Required because a previous cargo loss was reported.", ("losses", "yes"))]},
    {"name": "Commercial Property", "description": "Buildings, contents and business premises.", "questions": [
        ("entity", "Type of business entity", "text", None), ("hazmat", "Are hazardous materials present on the premises?", "yesno", None),
        ("manufacturing", "Is manufacturing carried out at this property?", "yesno", None), ("fire", "What fire protection is in place?", "select", ("manufacturing", "yes", ["Sprinkler system", "Fire extinguishers", "Alarm system", "None"])),
        ("claims", "Have there been property claims in the past five years?", "yesno", None), ("risk", "Risk classification", "select", (None, None, ["low", "medium", "high"])),
        ("hazmat_detail", "Describe the hazardous materials and how they are stored", "text", ("hazmat", "yes", None)),
    ], "requirements": [("Property details supporting document", "Required to understand the premises and insured property.", None), ("Fire safety documentation", "Required because fire protection or manufacturing activity needs review.", ("manufacturing", "yes")), ("Prior property claims history", "Required because previous property claims were reported.", ("claims", "yes"))]},
    {"name": "Commercial Auto", "description": "Vehicles and business fleets.", "questions": [
        ("vehicles", "How many vehicles are used in the business?", "number", None), ("vehicle_use", "What is the primary vehicle usage?", "select", (None, None, ["Delivery", "Service calls", "Passenger transport", "Other business use"])),
        ("radius", "What is the typical operating radius?", "select", (None, None, ["Local", "Regional", "National"])), ("drivers", "How many drivers operate business vehicles?", "number", None),
        ("accidents", "Have there been vehicle accidents or claims in the past five years?", "yesno", None), ("fleet_schedule", "Describe the fleet composition and vehicle values", "text", ("vehicles", ">1", None)),
        ("accident_history", "Describe the accident or claim history", "text", ("accidents", "yes", None))], "requirements": [("Vehicle schedule", "Required to identify vehicles used by the business.", None), ("Driver information", "Required to understand who operates the business vehicles.", None), ("Accident and claims history", "Required because prior accidents or claims were reported.", ("accidents", "yes"))]},
    {"name": "General Liability", "description": "Third-party injury and property risks.", "questions": [
        ("activity", "What is the primary business activity?", "text", None), ("visitors", "Do customers or visitors attend your premises?", "yesno", None),
        ("products", "Do you manufacture or sell products?", "yesno", None), ("subcontractors", "Do you use subcontractors?", "yesno", None), ("claims", "Have there been liability claims in the past five years?", "yesno", None),
        ("premises", "Describe the customer or visitor premises", "text", ("visitors", "yes", None)), ("product_detail", "Describe the products sold or manufactured", "text", ("products", "yes", None)),
        ("subcontractor_detail", "Describe subcontractor work and controls", "text", ("subcontractors", "yes", None))], "requirements": [("Business activity summary", "Required to understand the liability exposure.", None), ("Prior liability claims history", "Required because prior liability claims were reported.", ("claims", "yes")), ("Subcontractor information", "Required because subcontractors are used.", ("subcontractors", "yes"))]},
    {"name": "Professional Liability / E&O", "description": "Professional services and errors-and-omissions risks.", "questions": [
        ("service", "What professional services do you provide?", "text", None), ("clients", "What types of clients do you serve?", "text", None), ("professionals", "How many professionals provide services?", "number", None),
        ("financial_data", "Do services involve client financial or sensitive data?", "yesno", None), ("claims", "Have there been professional liability claims in the past five years?", "yesno", None),
        ("controls", "Describe controls used for client financial or sensitive data", "text", ("financial_data", "yes", None)), ("claim_history", "Describe prior professional liability claims", "text", ("claims", "yes", None))], "requirements": [("Professional services summary", "Required to understand the services being insured.", None), ("Prior claims history", "Required because prior professional liability claims were reported.", ("claims", "yes")), ("Client-data controls summary", "Required because services involve client financial or sensitive data.", ("financial_data", "yes"))]},
    {"name": "Cyber Insurance", "description": "Digital systems, data and cyber risks.", "questions": [
        ("pii", "Do you handle customer personal information?", "yesno", None), ("records", "Approximately how many customer records do you maintain?", "number", ("pii", "yes", None)),
        ("payment", "Do you process payment or card data?", "yesno", None), ("cloud", "Do you use cloud systems for critical business operations?", "yesno", None), ("mfa", "Is multi-factor authentication used for critical systems?", "yesno", None),
        ("backups", "Are critical systems backed up and tested?", "yesno", None), ("incident", "Have you had a cyber incident in the past five years?", "yesno", None), ("incident_history", "Describe the prior cyber incident and response", "text", ("incident", "yes", None))], "requirements": [("Cybersecurity controls questionnaire", "Required to understand digital security controls.", None), ("Incident history", "Required because a previous cyber incident was reported.", ("incident", "yes")), ("Access-control evidence", "Required because multi-factor authentication is not in place.", ("mfa", "no"))]},
    {"name": "Workers' Compensation", "description": "Employee workplace risks.", "questions": [
        ("roles", "Describe the main employee roles and job classifications", "text", None), ("payroll", "What is the annual payroll?", "number", None), ("locations", "Do employees work from more than one location?", "yesno", None),
        ("hazardous_work", "Do employees perform hazardous or manual work?", "yesno", None), ("safety", "Is there a documented workplace safety program?", "yesno", None), ("claims", "Have there been workplace injuries or claims in the past five years?", "yesno", None),
        ("hazard_detail", "Describe hazardous work, machinery, and safety controls", "text", ("hazardous_work", "yes", None)), ("claim_history", "Describe prior workplace injuries or claims", "text", ("claims", "yes", None))], "requirements": [("Employee and payroll information", "Required to understand workforce exposure.", None), ("Workplace claims history", "Required because prior workplace injuries or claims were reported.", ("claims", "yes")), ("Safety program information", "Required because hazardous or manual work is performed.", ("hazardous_work", "yes"))]},
    {"name": "Inland Marine / Goods & Equipment", "description": "Goods and equipment in transit or temporary storage.", "questions": [
        ("items", "What goods or equipment need coverage?", "text", None), ("value", "What is the approximate total value?", "number", None), ("transport", "Are goods or equipment transported regularly?", "yesno", None),
        ("storage", "Is temporary storage used during transit?", "yesno", None), ("security", "Describe storage and transit security controls", "text", None), ("losses", "Have there been losses in the past five years?", "yesno", None),
        ("transport_detail", "Describe transportation methods and frequency", "text", ("transport", "yes", None)), ("loss_history", "Describe previous losses", "text", ("losses", "yes", None))], "requirements": [("Goods or equipment schedule", "Required to identify property in transit or temporary storage.", None), ("Valuation information", "Required when values need underwriting review.", ("value", ">5000000")), ("Prior loss history", "Required because previous losses were reported.", ("losses", "yes"))]},
    {"name": "Crime / Fidelity", "description": "Employee theft and financial crime risks.", "questions": [
        ("cash", "Do employees handle cash, money, or valuable assets?", "yesno", None), ("payments", "Do you use electronic payment systems?", "yesno", None), ("segregation", "Are authorization and segregation-of-duties controls in place?", "yesno", None),
        ("incidents", "Have there been theft, fraud, or fidelity incidents in the past five years?", "yesno", None), ("cash_controls", "Describe cash and asset handling controls", "text", ("cash", "yes", None)),
        ("payment_controls", "Describe electronic payment approval controls", "text", ("payments", "yes", None)), ("incident_history", "Describe prior theft or fraud incidents", "text", ("incidents", "yes", None))], "requirements": [("Financial controls summary", "Required to understand financial-crime controls.", None), ("Cash-control documentation", "Required because employees handle cash or valuable assets.", ("cash", "yes")), ("Prior incident history", "Required because prior theft or fraud incidents were reported.", ("incidents", "yes"))]},
]

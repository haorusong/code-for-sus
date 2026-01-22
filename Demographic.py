import pandas as pd

# demographic codebook mapping
data = [
    ["Q22", "Age", 1, "18–24"],
    ["Q22", "Age", 2, "25–34"],
    ["Q22", "Age", 3, "35–44"],
    ["Q22", "Age", 4, "45–54"],
    ["Q22", "Age", 5, "55–64"],
    ["Q22", "Age", 6, "65–74"],
    ["Q22", "Age", 7, "75 or older"],
    ["Q23", "Gender", 1, "Male"],
    ["Q23", "Gender", 2, "Female"],
    ["Q23", "Gender", 3, "Non-binary / Third gender"],
    ["Q23", "Gender", 4, "Prefer not to say"],
    ["Q24", "Education", 1, "Less than high school"],
    ["Q24", "Education", 2, "High school graduate"],
    ["Q24", "Education", 3, "University/College"],
    ["Q24", "Education", 4, "Graduate degree"],
    ["Q24", "Education", 5, "Doctorate"],
    ["Q25", "Marital Status", 1, "Single"],
    ["Q25", "Marital Status", 2, "Married"],
    ["Q25", "Marital Status", 3, "Divorced"],
    ["Q25", "Marital Status", 4, "Widowed"],
    ["Q25", "Marital Status", 5, "Other"],
    ["Q26", "Household Size", 1, "1"],
    ["Q26", "Household Size", 2, "2"],
    ["Q26", "Household Size", 3, "3"],
    ["Q26", "Household Size", 4, "4"],
    ["Q26", "Household Size", 5, "More than 5"],
    ["Q27", "Household Income", 1, "$0–$9,999"],
    ["Q27", "Household Income", 2, "$10,000–$24,999"],
    ["Q27", "Household Income", 3, "$25,000–$49,999"],
    ["Q27", "Household Income", 4, "$50,000–$74,999"],
    ["Q27", "Household Income", 5, "$75,000–$99,999"],
    ["Q27", "Household Income", 6, "$100,000–$149,999"],
    ["Q27", "Household Income", 7, "$150,000+"],
    ["Q28", "Employment Status", 1, "Employed full time"],
    ["Q28", "Employment Status", 2, "Employed part time"],
    ["Q28", "Employment Status", 3, "Unemployed (looking for job)"],
    ["Q28", "Employment Status", 4, "Unemployed (not looking for job)"],
    ["Q28", "Employment Status", 5, "Retired"],
    ["Q28", "Employment Status", 6, "Student"],
    ["Q28", "Employment Status", 7, "Disabled"],
    ["Q29", "Living Area", 1, "Urban"],
    ["Q29", "Living Area", 2, "Suburban"],
    ["Q29", "Living Area", 3, "Rural"]
]

# create DataFrame and save
df = pd.DataFrame(data, columns=["Question Code", "Variable Label", "Numeric Code", "Category Label"])
df.to_excel("Demographic_Codebook.xlsx", index=False)
print("✅ Saved as Demographic_Codebook.xlsx")
from io import BytesIO
from openpyxl import Workbook
from backend.app.modules.digital_twin.domain.cobie_xlsx import parse_cobie_xlsx
def test_cobie_xlsx():
 wb=Workbook(); wb.active.title="Component"; wb.active.append(["Name"]); wb.active.append(["Pump"]); [wb.create_sheet(x).append(["Name"]) for x in ("System","Facility","Space","Type")]; b=BytesIO(); wb.save(b); r=parse_cobie_xlsx(b.getvalue()); assert r["valid"] and r["component_count"]==1

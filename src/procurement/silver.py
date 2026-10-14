import xml.etree.ElementTree as ET

ATOM = "http://www.w3.org/2005/Atom"

AMOUNT_FIELDS = ("estimated_amount", "total_amount", "tax_exclusive_amount")

DOCUMENT_KINDS = (
    ("legal", "LegalDocumentReference"),
    ("technical", "TechnicalDocumentReference"),
    ("additional", "AdditionalDocumentReference"),
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in el if _local(child.tag) == name]


def _findall(el: ET.Element | None, *path: str) -> list[ET.Element]:
    if el is None:
        return []
    current = [el]
    for name in path:
        current = [child for parent in current for child in _children(parent, name)]
    return current


def _find(el: ET.Element | None, *path: str) -> ET.Element | None:
    matches = _findall(el, *path)
    return matches[0] if matches else None


def _text(el: ET.Element | None, *path: str) -> str | None:
    node = _find(el, *path)
    if node is None or node.text is None:
        return None
    return node.text.strip() or None


def _number(el: ET.Element | None, *path: str) -> float | None:
    value = _text(el, *path)
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_code(value: str | None) -> str | None:
    if value is None:
        return None
    if value.isdigit():
        return str(int(value))
    return value


def empty_tender() -> dict:
    return {
        "folder_id": None,
        "title": None,
        "status_code": None,
        "detail_url": None,
        "organ_name": None,
        "organ_nif": None,
        "organ_city": None,
        "parent_organ_name": None,
        "contract_type_code": None,
        "contract_subtype_code": None,
        "estimated_amount": None,
        "total_amount": None,
        "tax_exclusive_amount": None,
        "currency": None,
        "cpv_codes": [],
        "nuts_code": None,
        "province": None,
        "procedure_code": None,
        "urgency_code": None,
        "submission_deadline_local": None,
        "criteria": [],
        "documents": [],
        "quality_errors": [],
    }


def quality_errors(tender: dict) -> list[str]:
    errors = []
    if not tender["folder_id"]:
        errors.append("missing_folder_id")
    if not tender["title"]:
        errors.append("missing_title")
    for field in AMOUNT_FIELDS:
        value = tender[field]
        if value is not None and value < 0:
            errors.append(f"negative_{field}")
    return errors


def _parse_criteria(status: ET.Element) -> list[dict]:
    criteria = []
    for position, node in enumerate(
        _findall(status, "TenderingTerms", "AwardingTerms", "AwardingCriteria")
    ):
        criteria.append(
            {
                "position": position,
                "type_code": _text(node, "AwardingCriteriaTypeCode"),
                "subtype_code": normalize_code(
                    _text(node, "AwardingCriteriaSubTypeCode")
                ),
                "description": _text(node, "Description"),
                "weight": _number(node, "WeightNumeric"),
                "note": _text(node, "Note"),
            }
        )
    return criteria


def _parse_documents(status: ET.Element) -> list[dict]:
    documents = []
    for kind, name in DOCUMENT_KINDS:
        for ref in _findall(status, name):
            documents.append(
                {
                    "kind": kind,
                    "file_name": _text(ref, "ID"),
                    "uri": _text(ref, "Attachment", "ExternalReference", "URI"),
                    "document_hash": _text(
                        ref, "Attachment", "ExternalReference", "DocumentHash"
                    ),
                    "type_code": None,
                }
            )
    for ref in _findall(status, "GeneralDocument", "GeneralDocumentDocumentReference"):
        documents.append(
            {
                "kind": "general",
                "file_name": _text(ref, "Attachment", "ExternalReference", "FileName"),
                "uri": _text(ref, "Attachment", "ExternalReference", "URI"),
                "document_hash": _text(
                    ref, "Attachment", "ExternalReference", "DocumentHash"
                ),
                "type_code": _text(ref, "DocumentTypeCode"),
            }
        )
    return documents


def parse_tender(raw_xml: str) -> dict:
    root = ET.fromstring(raw_xml)
    status = _find(root, "ContractFolderStatus")
    if status is None:
        raise ValueError("missing ContractFolderStatus")

    project = _find(status, "ProcurementProject")
    party = _find(status, "LocatedContractingParty", "Party")

    nif = None
    for identification in _findall(party, "PartyIdentification", "ID"):
        if identification.get("schemeName") == "NIF" and identification.text:
            nif = identification.text.strip()

    title_node = root.find(f"{{{ATOM}}}title")
    link_node = root.find(f"{{{ATOM}}}link")
    total_amount_node = _find(project, "BudgetAmount", "TotalAmount")

    cpv_codes = [
        el.text.strip()
        for el in status.iter()
        if _local(el.tag) == "ItemClassificationCode" and el.text
    ]

    deadline_date = _text(
        status, "TenderingProcess", "TenderSubmissionDeadlinePeriod", "EndDate"
    )
    deadline_time = _text(
        status, "TenderingProcess", "TenderSubmissionDeadlinePeriod", "EndTime"
    )
    deadline = None
    if deadline_date:
        deadline = (
            f"{deadline_date}T{deadline_time}" if deadline_time else deadline_date
        )

    tender = empty_tender()
    tender.update(
        {
            "folder_id": _text(status, "ContractFolderID"),
            "title": (
                title_node.text.strip()
                if title_node is not None and title_node.text
                else None
            )
            or _text(project, "Name"),
            "status_code": _text(status, "ContractFolderStatusCode"),
            "detail_url": link_node.get("href") if link_node is not None else None,
            "organ_name": _text(party, "PartyName", "Name"),
            "organ_nif": nif,
            "organ_city": _text(party, "PostalAddress", "CityName"),
            "parent_organ_name": _text(
                status,
                "LocatedContractingParty",
                "ParentLocatedParty",
                "PartyName",
                "Name",
            ),
            "contract_type_code": _text(project, "TypeCode"),
            "contract_subtype_code": _text(project, "SubTypeCode"),
            "estimated_amount": _number(
                project, "BudgetAmount", "EstimatedOverallContractAmount"
            ),
            "total_amount": _number(project, "BudgetAmount", "TotalAmount"),
            "tax_exclusive_amount": _number(
                project, "BudgetAmount", "TaxExclusiveAmount"
            ),
            "currency": total_amount_node.get("currencyID")
            if total_amount_node is not None
            else None,
            "cpv_codes": list(dict.fromkeys(cpv_codes)),
            "nuts_code": _text(project, "RealizedLocation", "CountrySubentityCode"),
            "province": _text(project, "RealizedLocation", "CountrySubentity"),
            "procedure_code": _text(status, "TenderingProcess", "ProcedureCode"),
            "urgency_code": _text(status, "TenderingProcess", "UrgencyCode"),
            "submission_deadline_local": deadline,
            "criteria": _parse_criteria(status),
            "documents": _parse_documents(status),
        }
    )
    tender["quality_errors"] = quality_errors(tender)
    return tender


def safe_parse_tender(raw_xml: str) -> dict:
    try:
        return parse_tender(raw_xml)
    except (ET.ParseError, ValueError, TypeError) as error:
        tender = empty_tender()
        tender["quality_errors"] = [f"parse_error: {error}"]
        return tender

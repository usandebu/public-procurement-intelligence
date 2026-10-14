from procurement.silver import parse_tender, quality_errors, safe_parse_tender

ENTRY = """<entry xmlns="http://www.w3.org/2005/Atom"
 xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"
 xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2"
 xmlns:cac-place-ext="urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2">
 <id>https://example.es/licitacionesPerfilContratante/1</id>
 <link href="https://example.es/detail/1"/>
 <title>Servicio de soporte</title>
 <updated>2026-10-13T19:16:52.770+02:00</updated>
 <cac-place-ext:ContractFolderStatus>
  <cbc:ContractFolderID>EXP-001</cbc:ContractFolderID>
  <cbc-place-ext:ContractFolderStatusCode>PUB</cbc-place-ext:ContractFolderStatusCode>
  <cac-place-ext:LocatedContractingParty>
   <cac:Party>
    <cac:PartyIdentification><cbc:ID schemeName="NIF">Q2802877G</cbc:ID></cac:PartyIdentification>
    <cac:PartyIdentification><cbc:ID schemeName="ID_PLATAFORMA">999</cbc:ID></cac:PartyIdentification>
    <cac:PartyName><cbc:Name>Organismo Ejemplo</cbc:Name></cac:PartyName>
    <cac:PostalAddress><cbc:CityName>Madrid</cbc:CityName></cac:PostalAddress>
   </cac:Party>
   <cac-place-ext:ParentLocatedParty>
    <cac:PartyName><cbc:Name>Ministerio Ejemplo</cbc:Name></cac:PartyName>
   </cac-place-ext:ParentLocatedParty>
  </cac-place-ext:LocatedContractingParty>
  <cac:ProcurementProject>
   <cbc:Name>Servicio de soporte</cbc:Name>
   <cbc:TypeCode>2</cbc:TypeCode>
   <cbc:SubTypeCode>1</cbc:SubTypeCode>
   <cac:BudgetAmount>
    <cbc:EstimatedOverallContractAmount currencyID="EUR">138000</cbc:EstimatedOverallContractAmount>
    <cbc:TotalAmount currencyID="EUR">72600</cbc:TotalAmount>
    <cbc:TaxExclusiveAmount currencyID="EUR">60000</cbc:TaxExclusiveAmount>
   </cac:BudgetAmount>
   <cac:RequiredCommodityClassification><cbc:ItemClassificationCode>72253000</cbc:ItemClassificationCode></cac:RequiredCommodityClassification>
   <cac:RequiredCommodityClassification><cbc:ItemClassificationCode>72250000</cbc:ItemClassificationCode></cac:RequiredCommodityClassification>
   <cac:RequiredCommodityClassification><cbc:ItemClassificationCode>72253000</cbc:ItemClassificationCode></cac:RequiredCommodityClassification>
   <cac:RealizedLocation>
    <cbc:CountrySubentity>Madrid</cbc:CountrySubentity>
    <cbc:CountrySubentityCode>ES300</cbc:CountrySubentityCode>
   </cac:RealizedLocation>
  </cac:ProcurementProject>
  <cac:TenderingTerms>
   <cac:AwardingTerms>
    <cac:AwardingCriteria>
     <cbc:AwardingCriteriaTypeCode>OBJ</cbc:AwardingCriteriaTypeCode>
     <cbc:Description>Oferta economica</cbc:Description>
     <cbc:AwardingCriteriaSubTypeCode>1</cbc:AwardingCriteriaSubTypeCode>
     <cbc:WeightNumeric>48</cbc:WeightNumeric>
    </cac:AwardingCriteria>
    <cac:AwardingCriteria>
     <cbc:AwardingCriteriaTypeCode>SUBJ</cbc:AwardingCriteriaTypeCode>
     <cbc:Description>Plan de trabajo</cbc:Description>
     <cbc:WeightNumeric>25</cbc:WeightNumeric>
     <cbc:Note>Hasta 25 puntos</cbc:Note>
    </cac:AwardingCriteria>
   </cac:AwardingTerms>
  </cac:TenderingTerms>
  <cac:TenderingProcess>
   <cbc:ProcedureCode>9</cbc:ProcedureCode>
   <cbc:UrgencyCode>1</cbc:UrgencyCode>
   <cac:TenderSubmissionDeadlinePeriod>
    <cbc:EndDate>2026-09-24</cbc:EndDate>
    <cbc:EndTime>10:30:00</cbc:EndTime>
   </cac:TenderSubmissionDeadlinePeriod>
  </cac:TenderingProcess>
  <cac:LegalDocumentReference>
   <cbc:ID>PCAP.pdf</cbc:ID>
   <cac:Attachment><cac:ExternalReference>
    <cbc:URI>https://example.es/pcap</cbc:URI><cbc:DocumentHash>h1</cbc:DocumentHash>
   </cac:ExternalReference></cac:Attachment>
  </cac:LegalDocumentReference>
  <cac:TechnicalDocumentReference>
   <cbc:ID>PPT.pdf</cbc:ID>
   <cac:Attachment><cac:ExternalReference><cbc:URI>https://example.es/ppt</cbc:URI></cac:ExternalReference></cac:Attachment>
  </cac:TechnicalDocumentReference>
  <cac-place-ext:GeneralDocument>
   <cac-place-ext:GeneralDocumentDocumentReference>
    <cbc:ID>doc-1</cbc:ID>
    <cbc:DocumentTypeCode>12</cbc:DocumentTypeCode>
    <cac:Attachment><cac:ExternalReference>
     <cbc:URI>https://example.es/acta</cbc:URI><cbc:FileName>Acta</cbc:FileName>
    </cac:ExternalReference></cac:Attachment>
   </cac-place-ext:GeneralDocumentDocumentReference>
  </cac-place-ext:GeneralDocument>
 </cac-place-ext:ContractFolderStatus>
</entry>"""


def test_parse_tender_reads_core_fields():
    tender = parse_tender(ENTRY)

    assert tender["folder_id"] == "EXP-001"
    assert tender["title"] == "Servicio de soporte"
    assert tender["status_code"] == "PUB"
    assert tender["detail_url"] == "https://example.es/detail/1"
    assert tender["organ_name"] == "Organismo Ejemplo"
    assert tender["organ_nif"] == "Q2802877G"
    assert tender["organ_city"] == "Madrid"
    assert tender["parent_organ_name"] == "Ministerio Ejemplo"
    assert tender["nuts_code"] == "ES300"
    assert tender["procedure_code"] == "9"
    assert tender["quality_errors"] == []


def test_parse_tender_reads_amounts_and_currency():
    tender = parse_tender(ENTRY)

    assert tender["estimated_amount"] == 138000.0
    assert tender["total_amount"] == 72600.0
    assert tender["tax_exclusive_amount"] == 60000.0
    assert tender["currency"] == "EUR"


def test_parse_tender_deduplicates_cpv_codes_keeping_order():
    assert parse_tender(ENTRY)["cpv_codes"] == ["72253000", "72250000"]


def test_parse_tender_joins_deadline_date_and_time():
    assert parse_tender(ENTRY)["submission_deadline_local"] == "2026-09-24T10:30:00"


def test_parse_tender_reads_awarding_criteria_with_weights():
    criteria = parse_tender(ENTRY)["criteria"]

    assert [c["description"] for c in criteria] == [
        "Oferta economica",
        "Plan de trabajo",
    ]
    assert [c["weight"] for c in criteria] == [48.0, 25.0]
    assert [c["type_code"] for c in criteria] == ["OBJ", "SUBJ"]
    assert criteria[1]["note"] == "Hasta 25 puntos"
    assert [c["position"] for c in criteria] == [0, 1]


def test_parse_tender_reads_documents_of_every_kind():
    documents = parse_tender(ENTRY)["documents"]

    assert [d["kind"] for d in documents] == ["legal", "technical", "general"]
    assert documents[0]["file_name"] == "PCAP.pdf"
    assert documents[0]["document_hash"] == "h1"
    assert documents[2]["file_name"] == "Acta"
    assert documents[2]["type_code"] == "12"


def test_quality_errors_flags_missing_ids_and_negative_amounts():
    tender = parse_tender(ENTRY)
    tender["folder_id"] = None
    tender["total_amount"] = -1.0

    assert quality_errors(tender) == ["missing_folder_id", "negative_total_amount"]


def test_safe_parse_tender_turns_broken_xml_into_a_rejection():
    tender = safe_parse_tender("<entry>")

    assert tender["folder_id"] is None
    assert tender["quality_errors"][0].startswith("parse_error")


def test_safe_parse_tender_rejects_entries_without_contract_folder():
    tender = safe_parse_tender('<entry xmlns="http://www.w3.org/2005/Atom"/>')

    assert tender["quality_errors"] == ["parse_error: missing ContractFolderStatus"]

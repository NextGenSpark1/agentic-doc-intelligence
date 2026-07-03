import type { SchemaField } from '../types'

export interface SchemaPreset {
  label: string
  fields: SchemaField[]
}

// Single source of truth for default extraction fields per case type.
// Mirrors the Pydantic models in backend/schemas/investigation.py.
// All preset fields have custom: false — only user-added fields are custom: true.
export const PRESET_SCHEMAS: Record<string, SchemaPreset> = {
  financial: {
    label: 'Financial Transaction',
    fields: [
      { name: 'vendor_name',      description: 'Name of the vendor or payee receiving funds',          is_array: false, custom: false },
      { name: 'amount',           description: 'Transaction or invoice amount as a number',            is_array: false, custom: false },
      { name: 'currency',         description: 'Three-letter currency code, e.g. MYR, USD',           is_array: false, custom: false },
      { name: 'bank_account',     description: 'Bank account number the payment was made to',         is_array: false, custom: false },
      { name: 'approval_officer', description: 'Name of the officer who approved the payment',        is_array: false, custom: false },
      { name: 'invoice_number',   description: 'Invoice or document reference number',                is_array: false, custom: false },
      { name: 'payment_date',     description: 'Date of payment in ISO format YYYY-MM-DD',            is_array: false, custom: false },
      { name: 'po_number',        description: 'Purchase order number linked to the payment',         is_array: false, custom: false },
    ],
  },

  payment_tracing: {
    label: 'Payment Tracing',
    fields: [
      { name: 'vendor_name',      description: 'Name of the vendor or payee receiving funds',          is_array: false, custom: false },
      { name: 'amount',           description: 'Transaction or invoice amount as a number',            is_array: false, custom: false },
      { name: 'currency',         description: 'Three-letter currency code, e.g. MYR, USD',           is_array: false, custom: false },
      { name: 'bank_account',     description: 'Bank account number the payment was made to',         is_array: false, custom: false },
      { name: 'approval_officer', description: 'Name of the officer who approved the payment',        is_array: false, custom: false },
      { name: 'invoice_number',   description: 'Invoice or document reference number',                is_array: false, custom: false },
      { name: 'payment_date',     description: 'Date of payment in ISO format YYYY-MM-DD',            is_array: false, custom: false },
      { name: 'po_number',        description: 'Purchase order number linked to the payment',         is_array: false, custom: false },
    ],
  },

  procurement_fraud: {
    label: 'Procurement Fraud',
    fields: [
      { name: 'tender_id',          description: 'Tender or solicitation identifier',                 is_array: false, custom: false },
      { name: 'awarded_vendor',     description: 'Vendor that won the tender',                        is_array: false, custom: false },
      { name: 'competing_vendors',  description: 'Other vendors that bid',                            is_array: true,  custom: false },
      { name: 'approval_timeline',  description: 'Key approval dates or sequence described',          is_array: false, custom: false },
      { name: 'budget_amount',      description: 'Approved budget for the procurement',               is_array: false, custom: false },
      { name: 'contract_value',     description: 'Final awarded contract value',                      is_array: false, custom: false },
    ],
  },

  conflict_of_interest: {
    label: 'Conflict of Interest',
    fields: [
      { name: 'person_names',      description: 'Names of individuals mentioned',                     is_array: true,  custom: false },
      { name: 'related_companies', description: 'Companies linked to the individuals',                is_array: true,  custom: false },
      { name: 'shareholders',      description: 'Named shareholders',                                 is_array: true,  custom: false },
      { name: 'directors',         description: 'Named directors',                                    is_array: true,  custom: false },
      { name: 'addresses',         description: 'Physical addresses mentioned',                       is_array: true,  custom: false },
      { name: 'phone_numbers',     description: 'Phone numbers mentioned',                            is_array: true,  custom: false },
    ],
  },

  communication: {
    label: 'Communication Intelligence',
    fields: [
      { name: 'dates',               description: 'Dates referenced in the communication',            is_array: true,  custom: false },
      { name: 'participants',        description: 'People involved in the conversation',              is_array: true,  custom: false },
      { name: 'intent_indicators',   description: 'Phrases signalling intent or agreement',           is_array: true,  custom: false },
      { name: 'suspicious_keywords', description: 'Terms suggesting irregularity',                    is_array: true,  custom: false },
      { name: 'commitments',         description: 'Promises or commitments made',                     is_array: true,  custom: false },
      { name: 'payment_references',  description: 'Amounts or payment references mentioned',          is_array: true,  custom: false },
    ],
  },

  financial_crime: {
    label: 'Financial Crime',
    fields: [
      { name: 'account_numbers',         description: 'Bank or financial account numbers mentioned',               is_array: true,  custom: false },
      { name: 'counterparties',          description: 'Individuals or entities on the other side of transactions', is_array: true,  custom: false },
      { name: 'transaction_amounts',     description: 'All transaction amounts mentioned',                         is_array: true,  custom: false },
      { name: 'flagged_transactions',    description: 'Transactions identified as suspicious or irregular',        is_array: true,  custom: false },
      { name: 'reporting_entity',        description: 'Entity that filed or submitted the report',                 is_array: false, custom: false },
      { name: 'investigation_reference', description: 'Reference number for this investigation or report',         is_array: false, custom: false },
    ],
  },

  corruption: {
    label: 'Corruption',
    fields: [
      { name: 'involved_parties',        description: 'Individuals or entities involved in the alleged corruption',    is_array: true,  custom: false },
      { name: 'benefit_value',           description: 'Value or amount of the benefit received or offered',            is_array: false, custom: false },
      { name: 'benefit_type',            description: 'Nature of the benefit (cash, contract, gift, etc.)',            is_array: false, custom: false },
      { name: 'relationship_type',       description: 'Relationship between the parties (official, contractor, etc.)', is_array: false, custom: false },
      { name: 'evidence_of_concealment', description: 'Evidence of attempts to hide or obscure the corruption',        is_array: false, custom: false },
      { name: 'jurisdiction',            description: 'Legal jurisdiction applicable to this case',                    is_array: false, custom: false },
    ],
  },

  audit: {
    label: 'Audit',
    fields: [
      { name: 'vendor_name',      description: 'Name of the vendor or payee receiving funds',          is_array: false, custom: false },
      { name: 'amount',           description: 'Transaction or invoice amount as a number',            is_array: false, custom: false },
      { name: 'currency',         description: 'Three-letter currency code, e.g. MYR, USD',           is_array: false, custom: false },
      { name: 'bank_account',     description: 'Bank account number the payment was made to',         is_array: false, custom: false },
      { name: 'approval_officer', description: 'Name of the officer who approved the payment',        is_array: false, custom: false },
      { name: 'invoice_number',   description: 'Invoice or document reference number',                is_array: false, custom: false },
      { name: 'payment_date',     description: 'Date of payment in ISO format YYYY-MM-DD',            is_array: false, custom: false },
      { name: 'po_number',        description: 'Purchase order number linked to the payment',         is_array: false, custom: false },
    ],
  },

  general: {
    label: 'General Document',
    fields: [
      { name: 'party_names',   description: 'All named parties in the document',                          is_array: true,  custom: false },
      { name: 'key_dates',     description: 'Important dates mentioned',                                  is_array: true,  custom: false },
      { name: 'key_amounts',   description: 'Financial amounts or values mentioned',                      is_array: true,  custom: false },
      { name: 'document_type', description: 'Type of document (contract, invoice, letter, etc.)',         is_array: false, custom: false },
      { name: 'signatories',   description: 'Individuals who signed or executed the document',            is_array: true,  custom: false },
      { name: 'key_clauses',   description: 'Important clauses or terms',                                 is_array: true,  custom: false },
    ],
  },
}

export const CASE_TYPE_OPTIONS = [
  { value: 'financial_crime',      label: 'Financial Crime' },
  { value: 'procurement_fraud',    label: 'Procurement Fraud' },
  { value: 'corruption',           label: 'Corruption' },
  { value: 'conflict_of_interest', label: 'Conflict of Interest' },
  { value: 'communication',        label: 'Communication Intelligence' },
  { value: 'payment_tracing',      label: 'Payment Tracing' },
  { value: 'audit',                label: 'Audit' },
  { value: 'general',              label: 'General Document' },
]

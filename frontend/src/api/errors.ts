/**
 * API Error Handling Utilities
 *
 * Centralized error processing for Backend responses.
 * Handles Pydantic validation errors, business logic errors, and service failures.
 */

import axios from 'axios';

// =============================================================================
// Error Types
// =============================================================================

/**
 * Normalized API error structure
 */
export interface ApiError {
  /** HTTP status code */
  status: number;
  /** Human-readable error message (German) */
  message: string;
  /** Affected field name (for validation errors) */
  field?: string;
  /** Error type for UI handling */
  type: 'validation' | 'business' | 'security' | 'service' | 'network' | 'unknown';
  /** Original error details for debugging */
  details?: unknown;
}

/**
 * Pydantic validation error detail structure
 */
interface PydanticValidationDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * Backend error response structure
 */
interface BackendErrorResponse {
  detail?: string | PydanticValidationDetail[];
  message?: string;
}

// =============================================================================
// Error Parsing
// =============================================================================

/**
 * Extract field name from Pydantic location array
 * ['body', 'message'] -> 'message'
 * ['body', 'history', 0, 'content'] -> 'history[0].content'
 */
function extractFieldName(loc: (string | number)[]): string {
  // Skip 'body' prefix if present
  const parts = loc.filter((part) => part !== 'body');

  return parts
    .map((part, index) => {
      if (typeof part === 'number') {
        return `[${part}]`;
      }
      return index === 0 ? part : `.${part}`;
    })
    .join('');
}

/**
 * Parse Pydantic validation error (HTTP 422)
 */
function parseValidationError(detail: PydanticValidationDetail[]): ApiError {
  if (!detail || detail.length === 0) {
    return {
      status: 422,
      message: 'Validierungsfehler: Ungültige Eingabe',
      type: 'validation',
    };
  }

  const firstError = detail[0];
  const fieldName = extractFieldName(firstError.loc);
  const message = firstError.msg;

  // Translate common Pydantic messages to German
  const translatedMessage = translateValidationMessage(message);

  return {
    status: 422,
    message: fieldName
      ? `Fehler in Feld "${fieldName}": ${translatedMessage}`
      : translatedMessage,
    field: fieldName || undefined,
    type: 'validation',
    details: detail,
  };
}

/**
 * Translate common Pydantic validation messages to German
 */
function translateValidationMessage(message: string): string {
  const translations: Record<string, string> = {
    'String should have at least 1 character': 'Darf nicht leer sein',
    'Field required': 'Pflichtfeld',
    'Input should be a valid string': 'Muss ein gültiger Text sein',
    'Input should be a valid integer': 'Muss eine ganze Zahl sein',
    'Input should be a valid number': 'Muss eine Zahl sein',
    'Input should be a valid list': 'Muss eine Liste sein',
    'Input should be a valid email address': 'Ungültige E-Mail-Adresse',
    'value is not a valid email address': 'Ungültige E-Mail-Adresse',
  };

  // Check for exact matches
  if (translations[message]) {
    return translations[message];
  }

  // Check for partial matches
  for (const [pattern, translation] of Object.entries(translations)) {
    if (message.toLowerCase().includes(pattern.toLowerCase())) {
      return translation;
    }
  }

  return message;
}

/**
 * Parse business logic or security error (HTTP 400, 403)
 */
function parseBusinessError(
  status: number,
  detail: string | undefined
): ApiError {
  const message = detail || 'Anfrage konnte nicht verarbeitet werden';

  // Translate common backend messages
  const translatedMessage = translateBusinessMessage(message);

  return {
    status,
    message: translatedMessage,
    type: status === 403 ? 'security' : 'business',
    details: detail,
  };
}

/**
 * Translate common backend business messages to German
 */
function translateBusinessMessage(message: string): string {
  // File extension errors
  if (message.includes('File extension') && message.includes('not allowed')) {
    const match = message.match(/'.(\w+)'/);
    const extension = match ? match[1] : 'dieser Typ';
    return `Dateityp .${extension} ist nicht erlaubt. Erlaubt sind: PDF, DOCX, TXT, MD`;
  }

  // Query not allowed
  if (message.includes('Query not allowed')) {
    return 'Diese Abfrage ist aus Sicherheitsgründen nicht erlaubt';
  }

  // Service unavailable
  if (message.includes('CRM nicht konfiguriert') || message.includes('CRM ist nicht konfiguriert')) {
    return 'CRM-Integration ist nicht konfiguriert. Bitte Administratoren kontaktieren.';
  }

  // Multiple statements
  if (message.includes('Multiple') && message.includes('statements')) {
    return 'Nur einzelne Abfragen sind erlaubt';
  }

  return message;
}

/**
 * Parse service unavailable error (HTTP 503)
 */
function parseServiceError(detail: string | undefined): ApiError {
  const message = detail || 'Service vorübergehend nicht verfügbar';

  return {
    status: 503,
    message: translateBusinessMessage(message),
    type: 'service',
    details: detail,
  };
}

// =============================================================================
// Main Error Parser
// =============================================================================

/**
 * Parse any error into a normalized ApiError structure.
 * Handles Axios errors, network errors, and unknown errors.
 */
export function parseApiError(error: unknown): ApiError {
  // Network error (no response)
  if (axios.isAxiosError(error) && !error.response) {
    return {
      status: 0,
      message: 'Netzwerkfehler: Server nicht erreichbar. Bitte Verbindung prüfen.',
      type: 'network',
      details: error.message,
    };
  }

  // Axios error with response
  if (axios.isAxiosError(error) && error.response) {
    const { status, data } = error.response;
    const responseData = data as BackendErrorResponse;

    switch (status) {
      case 422:
        // Pydantic validation error
        if (Array.isArray(responseData.detail)) {
          return parseValidationError(responseData.detail);
        }
        return {
          status: 422,
          message: typeof responseData.detail === 'string'
            ? responseData.detail
            : 'Validierungsfehler',
          type: 'validation',
          details: responseData,
        };

      case 400:
      case 403:
        // Business logic or security error
        return parseBusinessError(
          status,
          typeof responseData.detail === 'string' ? responseData.detail : undefined
        );

      case 404:
        return {
          status: 404,
          message: 'Ressource nicht gefunden',
          type: 'business',
          details: responseData,
        };

      case 500:
        return {
          status: 500,
          message: 'Interner Serverfehler. Bitte später erneut versuchen.',
          type: 'unknown',
          details: responseData,
        };

      case 503:
        return parseServiceError(
          typeof responseData.detail === 'string' ? responseData.detail : undefined
        );

      default:
        return {
          status,
          message: typeof responseData.detail === 'string'
            ? responseData.detail
            : `Fehler (HTTP ${status})`,
          type: 'unknown',
          details: responseData,
        };
    }
  }

  // Standard Error object
  if (error instanceof Error) {
    return {
      status: 0,
      message: error.message,
      type: 'unknown',
      details: error,
    };
  }

  // Unknown error type
  return {
    status: 0,
    message: 'Ein unbekannter Fehler ist aufgetreten',
    type: 'unknown',
    details: error,
  };
}

/**
 * Check if an error is a specific type
 */
export function isValidationError(error: ApiError): boolean {
  return error.type === 'validation';
}

export function isSecurityError(error: ApiError): boolean {
  return error.type === 'security';
}

export function isServiceError(error: ApiError): boolean {
  return error.type === 'service';
}

export function isNetworkError(error: ApiError): boolean {
  return error.type === 'network';
}

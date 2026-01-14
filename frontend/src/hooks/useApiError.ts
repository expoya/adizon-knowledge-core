/**
 * useApiError Hook
 *
 * Provides utilities for displaying API errors as toasts.
 * Integrates with the Sonner toast library.
 */

import { useCallback } from 'react';
import { toast } from 'sonner';
import { ApiError, parseApiError } from '../api/errors';
import { ApiRequestError } from '../api/client';

// =============================================================================
// Toast Styling by Error Type
// =============================================================================

interface ToastOptions {
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Get toast styling based on error type
 */
function getToastConfig(error: ApiError): ToastOptions {
  switch (error.type) {
    case 'validation':
      return {
        duration: 5000, // 5 seconds for validation errors
      };

    case 'security':
      return {
        duration: 8000, // Longer for security warnings
      };

    case 'service':
      return {
        duration: 6000,
        action: {
          label: 'Erneut versuchen',
          onClick: () => window.location.reload(),
        },
      };

    case 'network':
      return {
        duration: 8000,
        action: {
          label: 'Erneut versuchen',
          onClick: () => window.location.reload(),
        },
      };

    default:
      return {
        duration: 5000,
      };
  }
}

// =============================================================================
// Hook Definition
// =============================================================================

export interface UseApiErrorReturn {
  /**
   * Show an error toast for an API error.
   * Automatically extracts message from ApiRequestError or parses unknown errors.
   */
  showError: (error: unknown, customMessage?: string) => void;

  /**
   * Show a warning toast (for non-critical issues like service unavailable)
   */
  showWarning: (message: string, action?: ToastOptions['action']) => void;

  /**
   * Show a success toast
   */
  showSuccess: (message: string) => void;

  /**
   * Parse an error into ApiError format (for custom handling)
   */
  parseError: (error: unknown) => ApiError;
}

/**
 * Hook for handling API errors with toast notifications.
 *
 * @example
 * ```tsx
 * const { showError, showSuccess } = useApiError();
 *
 * const handleSubmit = async () => {
 *   try {
 *     await uploadDocument(file);
 *     showSuccess('Dokument hochgeladen!');
 *   } catch (error) {
 *     showError(error);
 *   }
 * };
 * ```
 */
export function useApiError(): UseApiErrorReturn {
  const showError = useCallback((error: unknown, customMessage?: string) => {
    let apiError: ApiError;

    // Extract ApiError from custom error class
    if (error instanceof ApiRequestError) {
      apiError = error.apiError;
    } else {
      apiError = parseApiError(error);
    }

    const message = customMessage || apiError.message;
    const config = getToastConfig(apiError);

    // Use different toast types based on error severity
    switch (apiError.type) {
      case 'service':
        // Service unavailable is a warning, not an error
        toast.warning(message, {
          duration: config.duration,
          action: config.action,
        });
        break;

      case 'validation':
        // Validation errors with field information
        toast.error(message, {
          duration: config.duration,
          description: apiError.field
            ? `Bitte korrigiere das Feld "${apiError.field}"`
            : undefined,
        });
        break;

      case 'security':
        // Security errors with warning icon
        toast.error(message, {
          duration: config.duration,
          description: 'Diese Aktion ist nicht erlaubt.',
        });
        break;

      case 'network':
        // Network errors with retry option
        toast.error(message, {
          duration: config.duration,
          action: config.action,
        });
        break;

      default:
        toast.error(message, {
          duration: config.duration,
        });
    }
  }, []);

  const showWarning = useCallback(
    (message: string, action?: ToastOptions['action']) => {
      toast.warning(message, {
        duration: 6000,
        action,
      });
    },
    []
  );

  const showSuccess = useCallback((message: string) => {
    toast.success(message, {
      duration: 3000,
    });
  }, []);

  const parseError = useCallback((error: unknown): ApiError => {
    if (error instanceof ApiRequestError) {
      return error.apiError;
    }
    return parseApiError(error);
  }, []);

  return {
    showError,
    showWarning,
    showSuccess,
    parseError,
  };
}

// =============================================================================
// Utility Functions (for use outside of React components)
// =============================================================================

/**
 * Show an error toast directly (without hook).
 * Use this in non-React code or one-off cases.
 */
export function showApiError(error: unknown, customMessage?: string): void {
  let apiError: ApiError;

  if (error instanceof ApiRequestError) {
    apiError = error.apiError;
  } else {
    apiError = parseApiError(error);
  }

  const message = customMessage || apiError.message;

  toast.error(message, {
    duration: 5000,
  });
}

/**
 * Get a user-friendly error message from any error.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    return error.apiError.message;
  }
  return parseApiError(error).message;
}

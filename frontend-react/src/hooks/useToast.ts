// Re-export from global ToastContext for backward compatibility.
// All existing callers continue to work — toasts now show everywhere.
export { useToast, type Toast } from '../contexts/ToastContext'

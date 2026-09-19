/** Structured context is retained for debug mode, never substituted for fallback UI. */
export type DiagnosticContext={sceneId?:string;nodeId?:string;expression?:string;asset?:string;plugin?:string;phase?:string};
export type RuntimeDiagnostic=DiagnosticContext&{message:string;stack?:string};
export function diagnosticOf(error:unknown,context:DiagnosticContext={}):RuntimeDiagnostic {
 const details=error instanceof Error&&'diagnostic'in error?(error as Error&{diagnostic:RuntimeDiagnostic}).diagnostic:{};
 return {...context,...details,message:error instanceof Error?error.message:String(error),stack:error instanceof Error?error.stack:undefined};
}
export function withDiagnostic(error:unknown,context:DiagnosticContext):Error&{diagnostic:RuntimeDiagnostic} {
 const wrapped=new Error(error instanceof Error?error.message:String(error),{cause:error}) as Error&{diagnostic:RuntimeDiagnostic};
 wrapped.name='InteractiveRuntimeError';wrapped.diagnostic=diagnosticOf(error,context);
 if(error instanceof Error&&error.stack)wrapped.stack=error.stack;
 return wrapped;
}

from strategery.strategic_logger import strategic_logger
from .base import BasePatch, PatchResult, PatchContext

class EmailPatch(BasePatch):
    """
    Strategic patch for Email channel and OAuth re-authentication resilience.
    Fixes BUG-197: 'InstalledAppFlow' object has no attribute 'run_console'.
    """
    
    @property
    def name(self) -> str:
        return "Email & OAuth Resilience"

    @property
    def required_symbols(self) -> list[str]:
        # We target the library method used by the core email channel
        return ["google_auth_oauthlib.flow.InstalledAppFlow"]

    def apply(self, context: PatchContext) -> PatchResult:
        result = PatchResult(patch_name=self.name, success=True)
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            # Redirect deprecated 'run_console' to 'run_local_server'
            if not hasattr(InstalledAppFlow, "run_console"):
                def _redirected_run_console(self_flow, *args, **kwargs):
                    strategic_logger.warning("OAuth: 'run_console' is deprecated. Redirecting to 'run_local_server(open_browser=False)'.")
                    # Force headless mode since run_console was likely used for headless environments
                    kwargs["open_browser"] = False
                    # port=0 allows the OS to pick an available port
                    if "port" not in kwargs: kwargs["port"] = 0
                    return self_flow.run_local_server(*args, **kwargs)
                
                InstalledAppFlow.run_console = _redirected_run_console
                strategic_logger.info("EmailPatch: OAuth run_console redirection applied.")
            
            result.affected_symbols.append("InstalledAppFlow.run_console")
            return result
        except Exception as e:
            import traceback
            result.success = False
            result.error_msg = str(e)
            result.traceback = traceback.format_exc()
            strategic_logger.error(f"Email patch error: {e}")
            return result

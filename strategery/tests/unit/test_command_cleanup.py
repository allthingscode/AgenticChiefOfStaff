from strategery.logic import subagent_logic

def test_harden_command_strips_chcp():
    """Verify that redundant chcp 65001 is stripped (BUG-168)."""
    # Case 1: With semicolon
    raw_cmd = "chcp 65001; python script.py"
    hardened = subagent_logic.harden_subagent_command(raw_cmd)
    assert "chcp 65001" not in hardened
    assert "python.exe" in hardened

    # Case 2: Without semicolon (trailing space)
    raw_cmd2 = "chcp 65001 python script.py"
    hardened2 = subagent_logic.harden_subagent_command(raw_cmd2)
    assert "chcp 65001" not in hardened2
    assert "python.exe" in hardened2

def test_harden_command_strips_output_encoding():
    """Verify that redundant $OutputEncoding is stripped (BUG-168)."""
    raw_cmd = "$OutputEncoding = [System.Text.Encoding]::UTF8; ls"
    hardened = subagent_logic.harden_subagent_command(raw_cmd)
    assert "OutputEncoding" not in hardened
    assert "ls" in hardened

def test_harden_command_strips_console_encoding():
    """Verify that redundant Console OutputEncoding is stripped (BUG-168)."""
    raw_cmd = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Date"
    hardened = subagent_logic.harden_subagent_command(raw_cmd)
    assert "Console" not in hardened
    assert "Get-Date" in hardened

def test_harden_command_strips_null_redirection():
    """Verify that redundant >$null is stripped (BUG-168)."""
    raw_cmd = "chcp 65001 >$null; whoami"
    hardened = subagent_logic.harden_subagent_command(raw_cmd)
    assert "chcp 65001" not in hardened
    assert ">$null" not in hardened
    assert "whoami" in hardened

def test_harden_command_complex_clutter():
    """Verify multiple clutter patterns are stripped in one go."""
    raw_cmd = "chcp 65001 >$null; $OutputEncoding = [System.Text.Encoding]::UTF8; python -m strategery.strategic_doctor"
    hardened = subagent_logic.harden_subagent_command(raw_cmd)
    assert "chcp 65001" not in hardened
    assert "OutputEncoding" not in hardened
    assert "strategic_doctor" in hardened
    assert "python.exe" in hardened

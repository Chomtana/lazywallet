from lazysandbox.rpc import ROOT, anvil_command


def test_root_is_repo_root():
    assert (ROOT / "pnpm-workspace.yaml").exists()


def test_anvil_command_without_block():
    assert anvil_command("https://rpc.example", None, 8545) == [
        "anvil", "--fork-url", "https://rpc.example", "--chain-id", "1", "--port", "8545",
    ]


def test_anvil_command_with_block():
    cmd = anvil_command("https://rpc.example", "21000000", 8645)
    assert cmd[-2:] == ["--fork-block-number", "21000000"]
    assert "8645" in cmd


def test_anvil_command_with_chain_id():
    assert anvil_command("https://rpc.example", None, 8546, 43114) == [
        "anvil", "--fork-url", "https://rpc.example", "--chain-id", "43114", "--port", "8546",
    ]

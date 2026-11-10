# Pontem quickstart

Go from nothing to a service running on your own device, managed by Pontem, in
about ten minutes. Claude Code does the work: it installs the `pontem` CLI, enrolls
your device, deploys a small web page with a config namespace, gives you a link to
it, walks you through changing its config, and connects Claude Code or Codex to
Pontem's MCP server so you can ask about your devices.

## What you need

- [Claude Code](https://docs.claude.com/en/docs/claude-code)
- A Pontem account, and the admin app URL for your organization
- A Linux device (x86_64 or ARM64) with systemd and Docker, reachable from your
  machine with `ssh` (a key or a password both work)

## Run it

In Claude Code:

```
/plugin marketplace add pontemai/quickstart
/plugin install pontem@pontem
```

Then:

```
/pontem:quickstart
```

Claude asks for your admin app URL and the device to use.

With the plugin installed, ask Claude for other Pontem work, like deploying an
app, changing config or setting up a registry, and the `cli` skill has it read
`pontem guide` first. `/pontem:cli` invokes it directly.

## What's here

| Path | What it is |
|---|---|
| `plugin/skills/quickstart/SKILL.md` | The steps Claude follows |
| `plugin/skills/cli/SKILL.md` | Has Claude read `pontem guide` before other Pontem work |
| `plugin/skills/quickstart/package/` | The compose package and config namespace it deploys |
| `app/` | Source for the `ghcr.io/pontemai/quickstart` image |

## How the page reads its device

The page shows its device as the Pontem API reports it. The skill creates a
service account with `devices:read`, stores a 30-day key as the tenant secret
`quickstart-api-key`, and passes it to the container through the `API_KEY`
config key. The container calls the API itself; the key never reaches the
browser. The page shows whether Pontem has a change the device hasn't applied
yet, and follows the device through its check-ins until Pontem reports it in
sync.

## Releasing the image

Push a tag `v<version>` to build `ghcr.io/pontemai/quickstart:<version>` for
amd64 and arm64. Update these to match: the image tag in
`plugin/skills/quickstart/package/docker-compose.yaml`, the version in
`version.yaml`, and the plugin version in `plugin/.claude-plugin/plugin.json`.

## License

Apache-2.0. See [LICENSE](LICENSE).

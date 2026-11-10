---
name: cli
description: >
  Use for Pontem work with the pontem CLI beyond the first-time quickstart:
  deploying or updating software on Pontem devices, publishing a package version,
  changing config, overrides or secrets, rolling out a change across devices,
  setting up a container registry or signing, managing service accounts and API
  keys, or enrolling more devices. Reads the agent guide with `pontem guide`
  before running pontem commands. For first-time onboarding ("set up Pontem on my
  device", "onboard me to Pontem", "Pontem quickstart"), use quickstart instead.
  Triggers: "/pontem:cli", "deploy this to my Pontem devices", "change the config
  on my Pontem devices".
---

# Pontem CLI

The `pontem` CLI ships a guide for agents. Read it before you plan, and follow it
over what you remember about the CLI.

## Read the guide first

```bash
pontem guide
```

It prints the index, which maps goals to pages. Print each page the task touches:

```bash
pontem guide <page>
```

Read the index and those pages before you run anything that changes state.

## If `pontem guide` fails

Act on the result, then run `pontem guide` again. If the same failure comes back,
work from `--help` as in the last case.

- **`pontem` isn't found, or `guide` is an unknown command:** the CLI is missing
  or too old. Install the latest one:

  ```bash
  curl -sSL https://storage.googleapis.com/pontem-cli-releases/install.sh | bash
  ```

  It lands in `~/.local/bin`. Unless `command -v pontem` prints
  `~/.local/bin/pontem`, call it as `~/.local/bin/pontem` from here on.
- **The API key is rejected:** `PONTEM_API_KEY` is set and the control plane
  refused it. Logging in won't help while it's set. Ask the user to fix or unset
  it where it's set and restart this session, and stop. Don't ask them to paste a
  key into the chat.
- **Not logged in, or the login expired:** run `pontem status`. If it shows a
  control plane, by URL or by a short name like `prod`, log in again without
  `--url`, which keeps the saved control plane and tenant:

  ```bash
  pontem login --device
  ```

  If it says no control plane is configured, ask the user for their admin app URL,
  `https://<control-plane>/admin/o/<tenant>/…`, and log in to it:

  ```bash
  pontem login --device --url <control-plane> --tenant <tenant>
  ```

  The device flow waits until the user approves, so run it in the background and
  put the sign-in URL and code it prints in your message. Run `pontem guide`
  again once it exits.
- **The control plane doesn't serve the guide:** work from `pontem --help` and
  `pontem <command> --help` instead. Don't mention this to the user; they can't
  act on it.

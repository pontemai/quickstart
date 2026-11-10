---
name: cli
description: >
  Use for Pontem work with the pontem CLI beyond the first-time quickstart:
  deploying or updating software on Pontem devices, publishing a package version,
  changing config, overrides or secrets, rolling out a change across devices, or
  setting up a container registry. Reads the agent guide with `pontem guide`
  before running pontem commands. For first-time onboarding ("set up Pontem on my
  device", "onboard me to Pontem", "Pontem quickstart"), use quickstart instead.
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

Act on the result, then run `pontem guide` again:

- **`pontem` isn't found:** install it:

  ```bash
  curl -sSL https://storage.googleapis.com/pontem-cli-releases/install.sh | bash
  ```

  It lands in `~/.local/bin`. If that isn't on `PATH`, call it as
  `~/.local/bin/pontem`.
- **`guide` is an unknown command:** the CLI is too old. Update it with
  `pontem update`.
- **The API key is rejected:** `PONTEM_API_KEY` is set and the control plane
  refused it. Logging in won't help while it's set; ask the user for a valid key.
- **Not logged in, or the login expired:** `pontem status` shows the saved control
  plane and tenant. If nothing is saved, ask the user for their admin app URL,
  `https://<control-plane>/admin/o/<tenant>/…`. Log in with the device flow. It
  waits until they approve, so run it in the background, put the sign-in URL and
  code it prints in your message, and run `pontem guide` again once it exits:

  ```bash
  pontem login --device --url <control-plane> --tenant <tenant>
  ```
- **The control plane doesn't serve the guide:** work from `pontem --help` and
  `pontem <command> --help` instead. Don't mention this to the user; they can't
  act on it.

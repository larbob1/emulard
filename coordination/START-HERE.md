# Start here — replacement AI chats

Use these six **universal starting prompts** when a developer chat reaches its conversation limit, is lost, or needs to be replaced. Each is a complete copy-and-paste prompt, independent of the previous conversation.

| AI | Role | Prompt | Workstream |
| --- | --- | --- | --- |
| AI 1 | Lead coordinator / memory | [ONBOARD-COORDINATOR.md](ONBOARD-COORDINATOR.md) | [#11](https://github.com/larbob1/emulard/issues/11) |
| AI 2 | Graphics / shaders / pipelines | [ONBOARD-GRAPHICS.md](ONBOARD-GRAPHICS.md) | [#12](https://github.com/larbob1/emulard/issues/12) |
| AI 3 | Performance / reliability | [ONBOARD-RELIABILITY.md](ONBOARD-RELIABILITY.md) | [#13](https://github.com/larbob1/emulard/issues/13) |
| AI 4 | Local runtime testing | [ONBOARD-LOCAL.md](ONBOARD-LOCAL.md) | [#27](https://github.com/larbob1/emulard/issues/27) |
| AI 5 | Storage / streaming / I/O | [ONBOARD-STORAGE.md](ONBOARD-STORAGE.md) | [#45](https://github.com/larbob1/emulard/issues/45) |
| AI 6 | CPU execution / HLE scheduling | [ONBOARD-CPU.md](ONBOARD-CPU.md) | [#46](https://github.com/larbob1/emulard/issues/46) |

## Replacing a chat

1. Stop using the old chat for that role so two agents do not claim the same work. If possible, ask it to post its latest checkpoint to its issue first.
2. Open the matching prompt, select **Raw** or copy its entire contents, and paste it as the first message in the new chat. Connect the same authorized GitHub access; for AI4, restore the authorized local environment separately.
3. The replacement agent must read the live repository, current decisions, issue handoffs, branch heads and CI, and resume its own latest task. It must not treat this index or the initial prompt as a frozen progress snapshot.
4. Tell it to continue. The prompts instruct each AI to keep a persistent GitHub checkpoint after substantive milestones so that the next replacement can recover even if the old chat ended abruptly.

The project owner retains priority and merge authority. Current local testing authorization is recorded in the coordination decisions and #27; never infer broader permission from this index. [AGENTS.md](../AGENTS.md) is the shared agreement. The six prompts are maintained on the coordination branch, not the novice-facing main branch.


Owner clarification (D23): AI4 is the only agent permitted access to the owner's computer, local files, local shell, local runtime and game installation. AI1/AI2/AI3/AI5/AI6 are GitHub-only with respect to the owner's machine; they may use their own isolated execution environments and authorized repository CI for title-free synthetic work, never remote-control, mount, inspect, or run commands on the owner's computer, directly or through another agent. Request sanitized evidence through #27; AI4 independently performs only currently authorized local tasks. No new local test authorization.

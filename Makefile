APP ?= dailyder-bot

.PHONY: deploy-bot logs-bot status-bot

deploy-bot:
	flyctl deploy -a $(APP)

logs-bot:
	flyctl logs -a $(APP)

status-bot:
	flyctl status -a $(APP)

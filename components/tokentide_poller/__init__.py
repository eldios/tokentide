import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import automation
from esphome.components.esp32 import add_idf_sdkconfig_option
from esphome.const import CONF_ID, CONF_TRIGGER_ID

CODEOWNERS = ["@eldios"]
DEPENDENCIES = ["network"]
AUTO_LOAD = ["json"]

tokentide_poller_ns = cg.esphome_ns.namespace("tokentide_poller")
TokentidePoller = tokentide_poller_ns.class_("TokentidePoller", cg.Component)
PollResultTrigger = tokentide_poller_ns.class_(
    "PollResultTrigger",
    automation.Trigger.template(
        cg.float_, cg.float_, cg.int64, cg.int64, cg.std_string, cg.int_
    ),
)
StatusResultTrigger = tokentide_poller_ns.class_(
    "StatusResultTrigger", automation.Trigger.template(cg.std_string)
)
PollAction = tokentide_poller_ns.class_("PollAction", automation.Action)
CheckStatusAction = tokentide_poller_ns.class_("CheckStatusAction", automation.Action)

OpenAIUsage = tokentide_poller_ns.class_("OpenAIUsage", cg.Component)
OpenAIResultTrigger = tokentide_poller_ns.class_(
    "OpenAIResultTrigger",
    automation.Trigger.template(cg.float_, cg.float_, cg.int64, cg.int64, cg.int_),
)
OpenAIPollAction = tokentide_poller_ns.class_("OpenAIPollAction", automation.Action)

CONF_TOKEN = "token"
CONF_PROBE_MODEL = "probe_model"
CONF_ON_RESULT = "on_result"
CONF_ON_ANTHROPIC_STATUS = "on_anthropic_status"
CONF_OPENAI = "openai"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCOUNT_ID = "account_id"
CONF_CLIENT_ID = "client_id"

# Codex CLI public OAuth client (codex-rs/login/src/auth/manager.rs,
# pub const CLIENT_ID); the refresh grant takes no client secret.
DEFAULT_OPENAI_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

OPENAI_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(OpenAIUsage),
        cv.Required(CONF_REFRESH_TOKEN): cv.string,
        cv.Required(CONF_ACCOUNT_ID): cv.string,
        cv.Optional(CONF_CLIENT_ID, default=DEFAULT_OPENAI_CLIENT_ID): cv.string,
        cv.Optional(CONF_ON_RESULT): automation.validate_automation(
            {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(OpenAIResultTrigger)}
        ),
    }
).extend(cv.COMPONENT_SCHEMA)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(TokentidePoller),
        cv.Required(CONF_TOKEN): cv.string,
        cv.Optional(CONF_PROBE_MODEL, default="claude-haiku-4-5-20251001"): cv.string,
        cv.Optional(CONF_ON_RESULT): automation.validate_automation(
            {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(PollResultTrigger)}
        ),
        cv.Optional(CONF_ON_ANTHROPIC_STATUS): automation.validate_automation(
            {cv.GenerateID(CONF_TRIGGER_ID): cv.declare_id(StatusResultTrigger)}
        ),
        cv.Optional(CONF_OPENAI): OPENAI_SCHEMA,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_token(config[CONF_TOKEN]))
    cg.add(var.set_probe_model(config[CONF_PROBE_MODEL]))
    add_idf_sdkconfig_option("CONFIG_MBEDTLS_CERTIFICATE_BUNDLE", True)
    # The OpenAI variable must exist before the on_result automations are
    # built: those may contain tokentide_poller.openai_poll, whose action
    # awaits this id (creating it afterwards deadlocks codegen).
    openai = config.get(CONF_OPENAI)
    if openai is not None:
        ovar = cg.new_Pvariable(openai[CONF_ID])
        await cg.register_component(ovar, openai)
        cg.add(ovar.set_refresh_token(openai[CONF_REFRESH_TOKEN]))
        cg.add(ovar.set_account_id(openai[CONF_ACCOUNT_ID]))
        cg.add(ovar.set_client_id(openai[CONF_CLIENT_ID]))
    for conf in config.get(CONF_ON_RESULT, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(
            trigger,
            [
                (cg.float_, "u5"),
                (cg.float_, "u7"),
                (cg.int64, "r5"),
                (cg.int64, "r7"),
                (cg.std_string, "status"),
                (cg.int_, "code"),
            ],
            conf,
        )
    for conf in config.get(CONF_ON_ANTHROPIC_STATUS, []):
        trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], var)
        await automation.build_automation(trigger, [(cg.std_string, "indicator")], conf)
    if openai is not None:
        for conf in openai.get(CONF_ON_RESULT, []):
            trigger = cg.new_Pvariable(conf[CONF_TRIGGER_ID], ovar)
            await automation.build_automation(
                trigger,
                [
                    (cg.float_, "u5"),
                    (cg.float_, "u7"),
                    (cg.int64, "r5"),
                    (cg.int64, "r7"),
                    (cg.int_, "code"),
                ],
                conf,
            )


@automation.register_action(
    "tokentide_poller.poll",
    PollAction,
    automation.maybe_simple_id({cv.GenerateID(): cv.use_id(TokentidePoller)}),
)
async def tokentide_poller_poll_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var


@automation.register_action(
    "tokentide_poller.check_status",
    CheckStatusAction,
    automation.maybe_simple_id({cv.GenerateID(): cv.use_id(TokentidePoller)}),
)
async def tokentide_poller_check_status_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var


@automation.register_action(
    "tokentide_poller.openai_poll",
    OpenAIPollAction,
    automation.maybe_simple_id({cv.GenerateID(): cv.use_id(OpenAIUsage)}),
)
async def tokentide_poller_openai_poll_to_code(config, action_id, template_arg, args):
    var = cg.new_Pvariable(action_id, template_arg)
    await cg.register_parented(var, config[CONF_ID])
    return var

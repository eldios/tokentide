import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID, CONF_PORT

CODEOWNERS = ["@eldios"]
DEPENDENCIES = ["network", "lvgl"]

tokentide_screenshot_ns = cg.esphome_ns.namespace("tokentide_screenshot")
TokentideScreenshot = tokentide_screenshot_ns.class_("TokentideScreenshot", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(TokentideScreenshot),
        cv.Optional(CONF_PORT, default=8081): cv.port,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_port(config[CONF_PORT]))

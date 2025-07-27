import html
import traceback
from contextlib import contextmanager, closing
from typing import Union, Any, Dict, Optional, cast, Generator

from nicegui import ui, Client
from nicegui.elements.card import Card
from nicegui.elements.tooltip import Tooltip

from modbus_client.device.device_config import DeviceConfig
from modbus_client.device.registers.device_register import DeviceHoldingRegister, IDeviceRegister
from modbus_client.device.registers.enum_definition import EnumDefinition
from modbus_client.device.registers.register_type import RegisterType
from modbus_client.registers.registers import EnumValue, FlagsCollection
from modbus_client.server.js_helpers import add_custom_js, js_copy_handler
from modbus_client.server.mytypes import Connector
from modbus_client.server.runtime_data import RuntimeData

UiElement = Any
TValue = Union[int, float, EnumValue, FlagsCollection, str]
TValueForSet = Union[int, float, EnumDefinition]
TValuesMap = Dict[str, TValue]


@contextmanager
def ui_card(title: str = "") -> Generator[Card, Any, None]:
    with ui.card() as c:
        if len(title) > 0:
            ui.label(text=title).style("font-size: 18px; font-weight: bold")
        yield c


notification_timeout = 1000


class UiState:
    def __init__(self, conn: Connector, config: DeviceConfig) -> None:
        self.conn = conn
        self.config = config

        self.is_loading = False
        self.write_unlocked = False


def append_context_menu(el: UiElement, reg: IDeviceRegister, value_str: str) -> None:
    with el:
        with ui.context_menu():
            ui.menu_item(f'Copy name').on('click', js_handler=js_copy_handler(reg.name))
            ui.menu_item(f'Copy address').on('click', js_handler=js_copy_handler(f"{reg.address}"))
            ui.menu_item(f'Copy value').on('click', js_handler=js_copy_handler(value_str))


def notify_positive(ui_el: UiElement, text: str) -> None:
    with ui_el:
        ui.notify(text, type="positive", timeout=notification_timeout)


def notify_negative(ui_el: UiElement, text: str) -> None:
    with ui_el:
        ui.notify(text, type="negative", timeout=notification_timeout)


def register_ui(runtime_data: RuntimeData) -> None:
    ui.add_css("""
.q-tooltip {
    font-size: 15px;
}

.mylabel {
    font-size: 12px;
    width: 200px;
    text-align: right;
}

.q-checkbox__label { 
    overflow-wrap: anywhere;
    font-size: 12px;
}
""", shared=True)
    add_custom_js()

    @ui.page('/')  # type: ignore
    async def ui_index(client: Client) -> None:
        await client.connected()

        conn = runtime_data.connector
        device_config = runtime_data.connector.modbus_device.get_device_config()
        state = UiState(conn, device_config)

        all_regs = conn.modbus_device.get_device_config().get_all_registers()

        input_registers = device_config.registers.input_registers + [x for x in device_config.registers.holding_registers if x.readonly]
        holding_registers = [x for x in device_config.registers.holding_registers if not x.readonly]

        async def read_data() -> Optional[TValuesMap]:
            try:
                with closing(conn.client_factory()) as device_client:
                    return await conn.modbus_device.read_registers(device_client, all_regs)
            except:
                traceback.print_exc()
                ui.notify(f"Unable to update fetch data", type="negative", timeout=notification_timeout)
                return None

        async def refresh() -> None:
            state.is_loading = True
            ui_vars.refresh(None)
            values = await read_data()
            state.is_loading = False
            ui_vars.refresh(values)

        def lock_write() -> None:
            state.write_unlocked = False
            ui_vars.refresh()

        def unlock_write() -> None:
            state.write_unlocked = True
            ui_vars.refresh()

        @ui.refreshable  # type: ignore
        def ui_vars(values) -> None:
            with ui.row():
                ui.button(text="Refresh all", on_click=refresh)
                if state.write_unlocked:
                    ui.button(text="Lock write", on_click=lock_write, color="warning")
                else:
                    ui.button(text="Unlock write", on_click=unlock_write, color="secondary")

            if state.is_loading:
                ui.spinner(size='lg')

            if values is None:
                return

            with ui.row():
                with ui_card("Input registers"):
                    for reg in input_registers:
                        with ui.column():
                            emit_view_control(state, values, reg)

                with ui_card("Holding registers"):
                    for reg in holding_registers:
                        with ui.column():
                            emit_edit_control(state, values, reg)

        ui_vars(None)

        await refresh()


def process_value_for_copy(val: TValue) -> str:
    if isinstance(val, EnumValue):
        return val.enum_name or str(val.enum_value)
    elif isinstance(val, EnumDefinition):
        return val.name or str(val.value)
    elif isinstance(val, bool):
        return "1" if val else "0"
    elif isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        return str(round(val, 8))
    elif isinstance(val, FlagsCollection):
        return ",".join((x.flag_name or str(x.flag_bit)) for x in val)
    elif isinstance(val, str):
        return val
    else:
        raise ValueError("invalid value")


def process_value_for_edit(val: TValue) -> str | float:
    if isinstance(val, EnumValue):
        return val.enum_value
    elif isinstance(val, EnumDefinition):
        return val.value
    elif isinstance(val, (int, bool)):
        return val
    elif isinstance(val, float):
        return round(val, 8)
    elif isinstance(val, str):
        return val
    else:
        raise ValueError("invalid value")


def emit_view_control(state: UiState, values: TValuesMap, reg: IDeviceRegister) -> None:
    conn = state.conn
    is_refreshing = False
    ui_root = None

    unit_str = "" if reg.unit is None else f" [{reg.unit}]"

    async def fn_refresh(ui_el: UiElement) -> None:
        nonlocal is_refreshing, ui_root
        try:
            is_refreshing = True
            ui_cont.refresh()

            with closing(conn.client_factory()) as device_client:
                current_value = await conn.modbus_device.read_register(device_client, reg)

            values[reg.name] = current_value

            notify_positive(ui_root, f"/{reg.name}/ refreshed with value /{ui_el.value}/")
        except:
            traceback.print_exc()
            notify_negative(ui_root, f"Unable to refresh /{reg.name}/")
        finally:
            is_refreshing = False
            ui_cont.refresh()

    @ui.refreshable  # type: ignore
    def ui_cont() -> None:
        value = values[reg.name]

        with ui.row(align_items="center"):
            # if reg.type == RegisterType.FLAGS:
            #     ui.separator()

            ui_el: UiElement
            if reg.type == RegisterType.BOOL:
                value = cast(bool, value)
                ui_el = ui.checkbox(text=reg.name, value=value)
                ui_el.props("dense outlined readonly").style("width: 200px")
            elif reg.type == RegisterType.ENUM:
                value = cast(EnumValue, value)
                ui_el = ui.input(reg.name, value=value.enum_name or "<unknown>").props("autogrow")
                ui_el.props("dense outlined readonly").style("width: 200px")
            elif reg.type == RegisterType.FLAGS:
                ui_el = ui.label(text=reg.name)
                ui_el.style("width: 200px")
            elif reg.type == RegisterType.STRING:
                value = cast(EnumValue, value)
                ui_el = ui.input(reg.name, value=cast(str, value)).props("autogrow")
                ui_el.props("dense outlined readonly").style("width: 200px")
            else:
                if isinstance(value, int):
                    value_str = str(value)
                elif isinstance(value, float):
                    value_str = str(round(value, 8))
                else:
                    raise ValueError("invalid value")

                ui_el = ui.input(reg.name, value=value_str + unit_str)
                ui_el.props("dense outlined readonly").style("width: 200px")

            value_copy_str = process_value_for_copy(value)

            add_tooltip_for_reg_value(ui_el, reg, value)
            append_context_menu(ui_el, reg, value_copy_str)

            # Refresh button
            el = ui.button(text="Refresh", on_click=lambda: fn_refresh(ui_el))
            if is_refreshing:
                el.props("disabled loading")

        if reg.type == RegisterType.FLAGS:
            with ui.column():
                flags_col = cast(FlagsCollection, value)
                assert reg.flags is not None
                for flag in reg.flags:
                    ui_el2 = ui.checkbox(text=flag.name, value=flag in flags_col)
                    ui_el2.props("dense")  # .style("width: 200px")

    with ui.element() as ui_root:
        ui_cont()


def emit_edit_control(state: UiState, values: Any, reg: DeviceHoldingRegister) -> None:
    conn = state.conn
    is_refreshing = False
    is_setting = False
    override_value = None
    ui_root = None

    unit_str = "" if reg.unit is None else f" [{reg.unit}]"

    async def fn_refresh() -> None:
        nonlocal is_refreshing
        nonlocal ui_root
        try:
            is_refreshing = True
            ui_cont.refresh()

            with closing(conn.client_factory()) as device_client:
                current_value = await conn.modbus_device.read_register(device_client, reg)

            values[reg.name] = current_value

            notify_positive(ui_root, f"/{reg.name}/ refreshed with value /{process_value_for_copy(current_value)}/")
        except:
            traceback.print_exc()
            traceback.print_exc()
            notify_negative(ui_root, f"Unable to refresh /{reg.name}/")
        finally:
            is_refreshing = False
            ui_cont.refresh()

    async def fn_set(new_value: TValueForSet, value_str: str | None = None) -> None:
        nonlocal is_setting
        nonlocal override_value
        nonlocal ui_root

        if value_str is None:
            value_str = str(new_value)

        try:
            is_setting = True
            override_value = new_value
            ui_cont.refresh()

            with closing(conn.client_factory()) as device_client:
                await conn.modbus_device.write_register(device_client, reg, new_value)
            values[reg.name] = new_value

            notify_positive(ui_root, f"/{reg.name}/ set to /{value_str}/")
        except:
            traceback.print_exc()
            notify_negative(ui_root, f"Unable to update /{reg.name}/ value to /{value_str}/")
        finally:
            is_setting = False
            override_value = None
            ui_cont.refresh()

    @ui.refreshable  # type: ignore
    def ui_cont() -> None:
        is_enabled = state.write_unlocked and not is_refreshing and not is_setting

        value = values[reg.name]
        if override_value:
            value = override_value

        ui_el: UiElement
        set_on_change = None
        if reg.type == RegisterType.BOOL:
            ui_el = ui.checkbox(reg.name, value=value)
            if is_enabled:
                ui_el.on_value_change(lambda sender: fn_set(sender.value))
            ui_el.props("dense outlined").style("width: 200px")
            ui_el.enabled = is_enabled
        elif reg.type == RegisterType.ENUM:
            assert reg.enum is not None
            value_to_enum = {x.value: x for x in reg.enum}

            ui_el = ui.select(label=reg.name, options={x.value: x.get_display() for x in reg.enum},
                              value=process_value_for_edit(value))
            if is_enabled:
                ui_el.on_value_change(lambda sender: fn_set(value_to_enum[sender.value], value_str=value_to_enum[sender.value].name))
            ui_el.props("dense outlined").style("width: 200px")
            if not is_enabled:
                ui_el.props("readonly")
        elif reg.type == RegisterType.FLAGS:
            raise Exception("not supported")
        else:
            if state.write_unlocked:
                value_control: int | float
                if isinstance(value, int):
                    value_control = value
                elif isinstance(value, float):
                    value_control = round(value, 8)
                else:
                    raise ValueError("invalid value")

                ui_el = ui.number(reg.name + unit_str, value=value_control)
                set_on_change = lambda _: fn_set(ui_el.value)
                if not is_enabled:
                    ui_el.props("readonly")
            else:
                ui_el = ui.input(reg.name, value=process_value_for_copy(value) + unit_str)
                ui_el.props("readonly")
            ui_el.props("dense outlined").style("width: 200px")

        value_copy_str = process_value_for_copy(value)

        add_tooltip_for_reg_value(ui_el, reg, value)
        append_context_menu(ui_el, reg, value_copy_str)

        # Refresh button
        el = ui.button(text="Refresh", on_click=lambda: fn_refresh())
        if is_refreshing or is_setting:
            el.props("disabled")
        if is_refreshing:
            el.props("loading")

        # Set button
        if state.write_unlocked and set_on_change is not None:
            el = ui.button(text="Set", on_click=set_on_change, color="warning")
            if is_refreshing or is_setting:
                el.props("disabled")
            if is_setting:
                el.props("loading")

    with ui.row(align_items="center") as ui_root:
        ui_cont()


def add_tooltip_for_reg_value(el: UiElement, reg: IDeviceRegister, value: TValue) -> None:
    with el:
        with Tooltip().props('''anchor="top left" self="bottom left" delay=500''').classes("text-body2"):
            lines = [
                f'<b>Name:</b> {html.escape(reg.name)}',
                f'<b>Address:</b> {reg.address} / {reg.type.value}',
                ""]

            unit_str = "" if reg.unit is None else f" [{reg.unit}]"

            if isinstance(value, EnumValue):
                lines.append(f"<b>Value:</b> {html.escape(value.format())}")
                if value.enum_display is not None:
                    lines.append(f"<i>{html.escape(value.enum_display)}</i>")
            elif isinstance(value, EnumDefinition):
                lines.append(f"<b>Value:</b> {html.escape(value.name)}")
                if value.display is not None:
                    lines.append(f"<i>{html.escape(value.display)}</i>")
            elif isinstance(value, bool):
                lines.append(f"<b>Value:</b> {'ON' if value else 'OFF'}")
            elif isinstance(value, int):
                lines.append(f"<b>Value:</b> {value}{unit_str}")
            elif isinstance(value, float):
                lines.append(f"<b>Value:</b> {round(value, 8)}{unit_str}")
            elif isinstance(value, FlagsCollection):
                values_str = "".join(f"<br/> {html.escape(x.format())}" for x in value)
                lines.append(f"<b>Value:</b> {values_str}")
            elif isinstance(value, str):
                lines.append(f"<b>Value:</b> {html.escape(value)}")
            else:
                raise ValueError("invalid value")

            if len(reg.description) > 0:
                lines.append("")
                lines.append(f'<b>Register description:</b><br/>{html.escape(reg.description)}')

            ui.html("<br/>".join(lines))


def add_tooltip(el: UiElement, tooltip_text: str) -> None:
    with el:
        Tooltip(tooltip_text).props('''anchor="top left" self="bottom left"''').classes("text-body2")

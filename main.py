from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, Label, Button, Static
from textual.widget import Widget
from textual.containers import HorizontalGroup
from textual.reactive import reactive
from textual.validation import Number, Integer
import time
import asyncio
import random


emojis = ["🌲", "🔥", "  "]

class SimulationInputGroup(HorizontalGroup):
    def __init__(self, input_grid):
        super().__init__()
        self.input_grid = input_grid

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Ignite p(%)", validators=Number(minimum=10e-4, maximum=100), id="ignite_p")
        yield Input(placeholder="Burning time(s)", validators=Number(minimum=10e-4), id="burning_t")
        yield Input(placeholder="Rows", validators=Integer(minimum=1, maximum=30), id="rows", value="10")
        yield Input(placeholder="Cols", validators=Integer(minimum=1, maximum=70), id="cols", value="10")
        yield Button("Start", id="start", variant="success", disabled=True)
        reset_btn = Button("Reset", id="reset", variant="warning")
        reset_btn.styles.display = "none"
        yield reset_btn

    def on_input_changed(self, event: Input.Changed):
        button = self.query_one(Button)
        if event.input.is_valid and event.input.id == "rows":
            self.input_grid.set_rows(int(event.input.value))
        elif event.input.is_valid and event.input.id == "cols":
            self.input_grid.set_cols(int(event.input.value))
        for input_ in self.query(Input):
            if not input_.value or not input_.is_valid:
                button.disabled = True
                return
        self.query_one(Button).disabled = False

class GridItem(Widget):
    value = reactive(0)

    def __init__(self, input_grid, r, c):
        super().__init__()
        self.input_grid = input_grid
        self.r = r
        self.c = c

    def render(self) -> str:
        return emojis[self.value]

    def on_click(self) -> None:
        self.value = 1 if self.value == 0 else 0
        self.input_grid.grid[self.r][self.c] = self.value
        if self.value == 0:
            self.input_grid.burning_tiles.remove((self.r, self.c))
        else:
            self.input_grid.burning_tiles.append((self.r, self.c))

class InputGrid(Widget):
    rows = 10
    cols = 10
    grid = reactive([[]])
    burning_tiles = []

    def compose(self) -> ComposeResult:
        self.update_grid(False)
        for row_i in range(self.rows):
            for col_i in range(self.cols):
                grid_item = GridItem(self, row_i, col_i)
                grid_item.value = self.grid[row_i][col_i]
                yield grid_item

    def set_rows(self, n):
        self.rows = n
        self.update_grid()

    def set_cols(self, n):
        self.cols = n
        self.update_grid()

    def rerender(self):
        to_mount = []
        for row_i in range(self.rows):
            for col_i in range(self.cols):
                grid_item = GridItem(self, row_i, col_i)
                grid_item.value = self.grid[row_i][col_i]
                to_mount.append(grid_item)

        self.mount(*to_mount)

    def update_grid(self, rerender=True):
        self.clear()

        self.styles.grid_size_rows = self.rows
        self.styles.grid_size_columns = self.cols
        self.styles.width = self.cols * 2 + 2
        self.styles.height = self.rows + 2
        self.burning_tiles = []
        new_grid = []
        for _ in range(self.rows):
            new_grid.append([0] * self.cols)
        self.grid = new_grid
        if rerender:
            self.rerender()

    def clear(self):
        for grid_item in self.query(GridItem):
            grid_item.remove()


class SimulationWindow(Static):
    simulation_matrix = reactive([[]])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def render(self) -> str:
        result = []
        for row in self.simulation_matrix:
            result.append("".join(map(lambda x: emojis[x], row)))

        return "\n".join(result)

class ForestFileSimulation(App):
    CSS_PATH = "forest_fire_sim.tcss"

    def __init__(self):
        super().__init__()
        self.input_grid = InputGrid()
        self.simulation = SimulationWindow()
        self.ignite_p = None
        self.burning_t = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("Enter the input values:")
        yield SimulationInputGroup(self.input_grid)
        yield self.input_grid
        yield self.simulation
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            if not self.input_grid.burning_tiles:
                return
            self.input_grid.clear()
            self.input_grid.styles.display = "none"

            self.simulation.simulation_matrix = self.input_grid.grid
            self.simulation.styles.width = self.input_grid.styles.width
            self.simulation.styles.height = self.input_grid.styles.height
            self.simulation.styles.display = "block"

            for input_ in self.query(Input):
                input_.disabled = True

            button = self.query("#start")
            button.set_styles("display: none;")
            button = self.query("#reset")
            button.set_styles("display: block;")

            ignite_p = self.query_one("#ignite_p", Input)
            burning_t = self.query_one("#burning_t", Input)
            self.ignite_p = float(ignite_p.value) / 100
            self.burning_t = float(burning_t.value)

            self.run_worker(self.start_simulation(), exclusive=True)

        if event.button.id == "reset":
            self.input_grid.styles.display = "block"
            self.input_grid.burning_tiles.clear()
            self.input_grid.update_grid()

            for input_ in self.query(Input):
                input_.disabled = False

            button = self.query("#start")
            button.set_styles("display: block;")
            button = self.query("#reset")
            button.set_styles("display: none;")

            await self.simulation.remove()
            self.simulation = SimulationWindow()
            await self.mount(self.simulation)
            self.ignite_p = None
            self.burning_t = None

    async def start_simulation(self):
        burning_tiles = {}
        exclude = set()
        for tile in self.input_grid.burning_tiles:
            burning_tiles[tile] = time.time()

        while burning_tiles:
            if self.input_grid.styles.display == "block":
                break
            temp = burning_tiles.copy()
            for tile, time_ in temp.items():
                r_i, c_i = tile
                coords_to_check = (
                    (r_i - 1, c_i), (r_i - 1, c_i - 1), (r_i, c_i - 1),
                    (r_i + 1, c_i), (r_i + 1, c_i + 1), (r_i, c_i + 1),
                    (r_i - 1, c_i + 1), (r_i + 1, c_i - 1), (r_i, c_i)
                )
                for r, c in coords_to_check:
                    if r < 0 or c < 0 or r >= self.input_grid.rows or c >= self.input_grid.cols:
                        continue

                    target_tile_time = burning_tiles.get((r, c))
                    if target_tile_time:
                        if time.time() - target_tile_time >= self.burning_t:
                            self.simulation.simulation_matrix[r][c] = 2
                            del burning_tiles[(r, c)]
                            exclude.add((r, c))
                        continue

                    if random.random() < self.ignite_p and (r, c) not in exclude:
                        burning_tiles[(r, c)] = time.time()
                        self.simulation.simulation_matrix[r][c] = 1

            self.simulation.refresh()
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    app = ForestFileSimulation()
    app.run()

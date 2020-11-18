from .plot_specs import (
    FigureSpec,
    AxesSpec,
    LineSpec,
    FigureSpecList,
    LineSpecList,
    GridSpecList,
    ImageStackSpecList,
)


def prompt_line_builder(run):
    """
    This is a simple example.

    This makes a hard-coded assumption that the data has columns "motor" and
    "det" in the primary stream.
    """

    def func(run):
        "Return any arrays x, y. They must be of equal length."
        # *Lazily* read the data so that large arrays are not loaded unless
        # the yare used.
        ds = run.primary.read()
        # Do any computation you want in here....
        return ds["motor"], ds["det"]

    axes_spec = AxesSpec("motor", "det")
    figure_spec = FigureSpec((axes_spec,), "det v motor")
    label = f"Scan {run.metadata['start']['scan_id']}"
    line_spec = LineSpec(func, run, axes_spec, {"label": label})

    return [figure_spec, line_spec]


class StreamingPlotBuilder:
    """
    Base class for streaming builders
    """

    def __init__(self):
        self.figures = FigureSpecList()
        self.lines = LineSpecList()
        self.grids = GridSpecList()
        self.image_stacks = ImageStackSpecList()
        ...

    def __call__(self, run):
        # Implement this in the subclass.
        ...


class LastNLines(StreamingPlotBuilder):
    """
    Plot y vs x for the last N runs.

    Parameters
    ----------
    x : string
        field name
    y : string
        field name
    N : int
        number of lines to show at once
    stream_name : string, optional
        Stream where fields x and y are found. Default is "primary".
    """

    def __init__(self, x, y, N, stream_name="primary"):
        super().__init__()
        # Stash these and expose them as read-only properties.
        self._N = int(N)
        self._x = x
        self._y = y
        self._stream_name = stream_name
        self._axes = None

    def new_plot(self):
        "Start a new plot, leaving the current one (if any) as is."
        # If we already have a plot, forget about it and its lines. We just
        # want to forget about them, not *remove* them from the Viewer, so we
        # will block notification of the removal.
        if self._axes is not None:
            with self.figures.events.removed.blocker(), self.lines.events.removed.blocker():
                self.figures.clear()
                self.lines.clear()
        axes_spec = AxesSpec(self.x, self.y)
        figure_spec = FigureSpec((axes_spec,), f"{self.y} v {self.x}")
        self.figures.append(figure_spec)
        self._axes = axes_spec

    def _add_line(self, run):
        # Create a plot if we do not have one.
        if not self.figures:
            self.new_plot()
        # If necessary, removes lines to make room for the new line.
        while len(self.lines) >= self.N:
            self.lines.pop()

        stream_name = self.stream_name
        x = self.x
        y = self.y

        def func(run):
            # *Lazily* read the data so that large arrays are not loaded unless
            # the yare used.
            ds = run[stream_name].to_dask()
            return ds[x], ds[y]

        label = f"Scan {run.metadata['start']['scan_id']}"
        line_spec = LineSpec(func, run, self._axes, {"label": label})

        self.lines.append(line_spec)

    def __call__(self, run):
        # If the stream of interest is defined already, plot now.
        if self.stream_name in run:
            self._add_line(run)
        else:
            # Otherwise, connect a callback to run when the stream of interest arrives.
            run.events.new_stream.connect(self._on_new_stream)
            run.events.completed.disconnect(self._on_new_stream)

    def _on_new_stream(self, event):
        "This callback runs whenever BlueskyRun has a new stream."
        if event.name == self.stream_name:
            self._add_line(event.run)

    # Read-only properties so that these settings are inspectable, but not
    # changeable.

    @property
    def N(self):
        return self._N

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def stream_name(self):
        return self._stream_name
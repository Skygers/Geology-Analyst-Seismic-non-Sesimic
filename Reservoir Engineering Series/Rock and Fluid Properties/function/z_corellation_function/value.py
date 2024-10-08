from scipy import optimize
import numpy as np
import matplotlib.pyplot as plt
import sys
sys.path.append("Reservoir Engineering Series\Rock and Fluid Properties")
from function.pseudocritical.piper import Piper
from function.pseudocritical.sutton import Sutton
from function.z_corellation_function.dranchuk_kaseem import DAK
from function.z_corellation_function.hall_yarborough import hall_yarborough
from function.z_corellation_function.londono import londono
from function.z_corellation_function.kareem import kareem



models = {
    'DAK': DAK,
    'hall_yarborough': hall_yarborough,
    'londono': londono,
    'kareem': kareem,
}
MODEL_RANGES = {
    'DAK': {
        'Tr': (1, 3),
        'Pr': (0.2, 30)
    },
    'hall_yarborough': {
        'Tr': (1, 3),
        'Pr': (0.2, 20.5)
    },
    'londono': {
        'Tr': (1, 3),
        'Pr': (0.2, 30)
    },
    'kareem': {
        'Tr': (1, 3),
        'Pr': (0.2, 15)
    },
}


def _check_working_Pr_Tr_range(Pr, Tr, zmodel_str):
    Pr_is_in_range = np.logical_and(Pr >= MODEL_RANGES[zmodel_str]['Pr'][0], Pr <= MODEL_RANGES[zmodel_str]['Pr'][1]).all()
    Tr_is_in_range = np.logical_and(Tr >= MODEL_RANGES[zmodel_str]['Tr'][0], Tr <= MODEL_RANGES[zmodel_str]['Tr'][1]).all()

    #print(Pr >= MODEL_RANGES[zmodel_str]['Pr'][0], Pr <= MODEL_RANGES[zmodel_str]['Pr'][1])

    return Pr_is_in_range and Tr_is_in_range


zmodels_ks = '["DAK", "hall_yarborough", "londono", "kareem"]'
pmodels_ks = '["sutton", "piper"]'


def _get_guess_constant():
    return 0.900000765321234598723486


def _get_z_model(model='DAK'):

    if model not in models.keys():
        raise KeyError(
            'Z-factor model "%s" is not implemented. Choose from the list of available models: %s' % (model, zmodels_ks)
        )

    return models[model]


def _construct_guess_list_order(guess):
    """reorder t in an order closest to the provided guess"""
    t = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

    reordered = [guess]
    count = 0
    while len(t) > 0:
        match = min(t, key=lambda x: abs(x - guess))
        t.pop(t.index(match))
        reordered.append(match)
        count += 1
    return list(set(reordered))

def _calc_z_explicit_implicit_helper(Pr, Tr, zmodel_func, zmodel_str, guess, newton_kwargs, smart_guess):

    maxiter = 50
    Z = None
    smart_guess_model = 'kareem'

    # Explicit models
    if zmodel_str in ['kareem']:
        Z = zmodel_func(Pr=Pr, Tr=Tr)

    # Implicit models: they require iterative convergence
    else:

        if guess is None:
            if Pr < 15:
                guess = 0.9
            else:
                # Todo: z-factor after Pr shows linear trend. So fit a linear regression model for each TR and get
                #  better estimate of initial guess for Pr range greater than 15, which is the working bound of the
                #  explicit "kareem" model. But for now, guess = 2 gets the job done
                guess = 2
        if smart_guess is None:
            smart_guess = True

        worked = False

        if smart_guess:
            # if Pr and Tr is in the range of the "smart_guess_model" (explicit z-model), use that to make first guess
            if _check_working_Pr_Tr_range(Pr, Tr, smart_guess_model):
                guess_zmodel_func = _get_z_model(model=smart_guess_model)
                guess_ = guess_zmodel_func(Pr=Pr, Tr=Tr)
                guesses = [guess_] + [guess] + _construct_guess_list_order(guess)
            else:
                guesses = [guess] + _construct_guess_list_order(guess)

        else:
            guesses = _construct_guess_list_order(guess)

        for guess_ in guesses:
            try:
                if newton_kwargs is None:  # apply default value of max iteration if newton_kwargs is not provided
                    Z = optimize.newton(zmodel_func, guess_, args=(Pr, Tr), maxiter=maxiter)
                else:
                    if 'maxiter' in newton_kwargs:
                        Z = optimize.newton(zmodel_func, guess_, args=(Pr, Tr), **newton_kwargs)
                    else:
                        newton_kwargs.pop('maxiter', None)
                        Z = optimize.newton(zmodel_func, guess_, args=(Pr, Tr), maxiter=maxiter, **newton_kwargs)
                worked = True
            except:
                pass
            if worked:
                break

        if not worked:
            raise RuntimeError("Failed to converge")

    return Z



def calc_z(sg=None, P=None, T=None, H2S=None, CO2=None, N2=None, Pr=None, Tr=None, pmodel='piper', zmodel='DAK',
           guess=None, newton_kwargs=None, smart_guess=None, ps_props=False, ignore_conflict=False, **kwargs):
    """
    Calculates the gas compressibility factor, :math:`Z`.

    **Basic (most common) usage:**

    >>> import gascompressibility as gc
    >>>
    >>> gc.calc_z(sg=0.7, T=75, P=2010)
    0.7366562810878984


    **In presence of significant non-hydrocarbon impurities:**

    >>> gc.calc_z(sg=0.7, T=75, P=2010, CO2=0.1, H2S=0.07, N2=0.05)
    0.7765149771306533

    **When pseudo-critical properties are known (not common):**

    >>> gc.calc_z(Pr=1.5, Tr=1.5)
    0.859314380561347

    **Picking correlation models of your choice**

    >>> gc.calc_z(sg=0.7, T=75, P=2010, zmodel='kareem', pmodel='sutton')
    0.7150183342641309

    **Returning all associated pseudo-critical properties computed**

    >>> gc.calc_z(sg=0.7, T=75, P=2010, ps_props=True)
    {'z': 0.7366562810878984, 'Tpc': 371.4335560823552, 'Ppc': 660.6569792741872, 'J': 0.56221847, 'K': 14.450840999999999, 'Tr': 1.4394768357478496, 'Pr': 3.0646766226921294}



    Parameters
    ----------
    sg : float
        specific gravity of gas (dimensionless)
    P : float
        pressure of gas (psig)
    T : float
        temperature of gas (°F)
    H2S : float
        mole fraction of H2S (dimensionless)
    CO2 : float
        mole fraction of CO2 (dimensionless)
    N2 : float
        mole fraction of N2 (dimensionless). Available only when ``pmodel='piper'`` (default)
    Pr : float
        pseudo-reduced pressure, Pr (dimensionless)
    Tr : float
        pseudo-reduced temperature, Tr (dimensionless)
    pmodel : str
        choice of a pseudo-critical model.
        Check :ref:`Theories 1: Pseudo-Critical Property Models <theories:1. Pseudo-Critical Property Models>` for more information.
        Accepted inputs: ``'sutton'`` | ``'piper'``

        See Also
        --------
        ~sutton.Sutton
        ~piper.Piper

    zmodel : str
        choice of a z-correlation model.
        Check :ref:`Theories 2: Z-Factor Correlation Models <theories:2. Z-Factor Correlation Models>` for more information.
        Accepted inputs: ``'DAK'`` | ``'hall_yarborough'`` | ``'londono'`` |``'kareem'``
    guess : float
        initial guess of z-value for z-correlation models using iterative convergence (``'DAK'`` | ``'hall_yarborough'`` | ``'londono'``).
        NOT RECOMMENDED to manually set this parameter unless the computed :math:`P_r` exceeds 15. If so a default ``guess=2`` is applied, which
        is a good estimate for high-pressure scenarios. Otherwise for :math:`P_r < 15`, the built-in ``smart_guess`` takes over to
        automatically provide a good initial guess that's fast and accurate.
    newton_kwargs : dict
        dictonary of keyword-arguments used by ``scipy.optimize.newton`` method for z-correlation models that use
        iterative convergence (``'DAK'`` | ``'hall_yarborough'`` | ``'londono'``).

        >>> gc.calc_z(sg=0.7, P=2010, T=75, newton_kwargs={'maxiter': 10000})
        0.7366562810878984

        See Also
        ----------
        `scipy.optimize.newton <https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.newton.html>`_.
    smart_guess : bool
        ``True`` by default. Prevents rare corner cases where ``scipy.optimize.newton`` fails to converge to a true
        solution, and improves speed. It provides *"smart"* initial guess with explicit z-models (like ``zmodel='kareem'``)
        for :math:`P_r < 15`. For :math:`P_r > 15`, smart guess is turned off and uses a fixed value of ``guess=2``,
        which is shown to work well. Check :ref:`Theories 2.6: Caveats <theories:2.6. Caveats>` for more information.
    ps_props : bool
        set this to `True` to return a dictionary of all associated pseudo-critical properties computed during calculation
        of the z-factor.
    ignore_conflict : bool
        set this to True to override calculated variables with input keyword arguments.
    kwargs : dict
        optional kwargs used by pseudo-critical models (:doc:`Sutton <sutton>` | :doc:`Piper <piper>`) that allow direct calculation of
        z-factor from pseudo-critical properties instead of specific gravity correlation. Consider the below code example
        that uses ``pmodel='sutton'``:

        >>> gc.calc_z(Ppc=663, e_correction=21, Tpc=377.59, P=2010, T=75, pmodel='sutton', ignore_conflict=True)
        0.7720015496503527

        ``Ppc``, ``e_correction``, ``Tpc`` aren't default parameters defined in this function,
        but they can be optionally passed into Sutton's :ref:`Sutton.calc_Pr <Sutton.calc_Pr>` and :ref:`Sutton.calc_Tr <Sutton.calc_Tr>`
        methods if you already know these values (not common) and would like to compute the z-factor from these instead
        of using specific gravity correlation.


        Danger
        -------
        It is not recommended to the pass optional ``**kwargs`` unless you really know what you are doing. 99.9% of the users
        should not be using this feature.

    Returns
    -------
    float
        gas compressibility factor, :math:`Z` (dimensionless)

    """

    if zmodel in ['kareem']:
        if guess is not None:
            raise KeyError('calc_z(model="%s") got an unexpected argument "guess"' % zmodel)
        if newton_kwargs is not None:
            raise KeyError('calc_z(model="%s") got an unexpected argument "newton_kwargs"' % zmodel)
        if smart_guess is not None:
            raise KeyError('calc_z(model="%s") got an unexpected argument "smart_guess"' % zmodel)

    z_model = _get_z_model(model=zmodel)

    # Pr and Tr are already provided:
    if Pr is not None and Tr is not None:
        Z = _calc_z_explicit_implicit_helper(Pr, Tr, z_model, zmodel, guess, newton_kwargs, smart_guess)
        if ps_props is True:
            ps_props = {'z': Z, 'Pr': Pr, 'Tr': Tr}
            return ps_props
        else:
            return Z

    # Pr and Tr are NOT provided:
    if pmodel == 'piper':
        pc_instance = Piper()
        Tr, Pr = pc_instance._initialize_Tr_and_Pr(sg=sg, P=P, T=T, Tr=Tr, Pr=Pr, H2S=H2S, CO2=CO2, N2=N2, ignore_conflict=ignore_conflict, **kwargs)
    elif pmodel == 'sutton':
        if N2 is not None:
            raise KeyError('pmodel="sutton" does not support N2 as input. Set N2=None')
        pc_instance = Sutton()
        Tr, Pr = pc_instance._initialize_Tr_and_Pr(sg=sg, P=P, T=T, Tr=Tr, Pr=Pr, H2S=H2S, CO2=CO2, ignore_conflict=ignore_conflict, **kwargs)
    else:
        raise KeyError(
            'Pseudo-critical model "%s" is not implemented. Choose from the list of available models: %s' % (pmodel, pmodels_ks)
        )

    Z = _calc_z_explicit_implicit_helper(Pr, Tr, z_model, zmodel, guess, newton_kwargs, smart_guess)

    if ps_props is True:
        ps_props = {'z': Z}
        ps_props.update(pc_instance.ps_props)
        ps_props['Tr'] = Tr
        ps_props['Pr'] = Pr
        return ps_props
    else:
        return Z


def quickstart(
        zmodel='DAK',
        prmin=0.2,
        prmax=30,
        figsize=(8, 5),
        title_bold=None,
        title_plain=None,
        title_underline_loc=0.93,
        disable_tr_annotation=False,
        **kwargs
):
    """
    Quick plot generation tool for those who don't wish to write a full-blown matplotlib script. It generates a
    z-factor correlation plot against :math:`P_r` and :math:`T_r` ranges.

    **Basic usage**

    >>> import gascompressibility as gc
    >>>
    >>> result, fig, ax = gc.quickstart()

    .. figure:: _static/quickstart_1.png
        :align: center

    **Built-In Parameter Tweaks**

    >>> result, fig, ax = gc.quickstart(
    ...     zmodel='londono', prmin=3, prmax=12, figsize= (8, 4),
    ...     title_underline_loc=0.91, disable_tr_annotation=True,
    ...     title_bold='This is a bold title', title_plain='and this a plain',
    ... )

    .. figure:: _static/quickstart_2.png
        :align: center

    **Custimization using the returned matplotlib axis object**

    >>> result, fig, ax = gc.quickstart()
    >>>
    >>> ax.set_ylim(0, 2)
    >>> ax.set_xlim(0, 15)
    >>> ax.set_ylabel('This is a Y label')
    >>> ax.set_xlabel('This is a X label')
    >>> ax.grid(False)
    >>> ax.minorticks_off()
    >>> ax.text(0.1, 0.08, 'This is custom annotation', fontsize=11,
    ... transform=ax.transAxes)
    >>> ax.axvspan(9, 15, facecolor='#efefef', alpha=0.5)
    >>> ax.axvline(x=9, color='k', linestyle='--', linewidth=1, alpha=0.7)
    >>> ax.text(9.2, 1.9, 'Another custom annotation', fontsize=10, va='top',
    ... color='k', alpha=0.7, rotation=270)
    >>>
    >>> fig.tight_layout()
    >>> # fig.savefig('output.png', bbox_inches='tight', dpi=200)

    .. figure:: _static/quickstart_3.png
        :align: center

    **Extreme failure scenario when** ``smart_guess=False`` **and bad** ``guess`` **is provided - NOT RECOMMENDED**.
    Check :ref:`Theories 2.6: Caveats <theories:2.6. Caveats>` for more information.

    >>> results, fig, ax = gc.quickstart(zmodel='hall_yarborough', prmin=0.2, prmax=30,
    ... smart_guess=False, guess=0.1)

    .. figure:: _static/quickstart_10.png
        :align: center

    Parameters
    ----------
    zmodel : str
        choice of a z-correlation model.
        Check :ref:`Theories 2: Z-Factor Correlation Models <theories:2. Z-Factor Correlation Models>` for more information.
        Accepted inputs: ``'DAK'`` | ``'hall_yarborough'`` | ``'londono'`` |``'kareem'``
    prmin : float
        minimum value of the :math:`P_r` range
    prmax : float
        maximum value of the :math:`P_r` range
    figsize : tuple
        matplotlib figure size
    title_bold : str
        string of the bold (left) portion of the figure title
    title_plain : str
        string of the plain (right) portion of the figure title
    title_underline_loc : float
        vertical location of the horizontal bar under the title. Try adjusting this value between 0.8 ~ 1.10 if the
        title underline looks off
    disable_tr_annotation : bool
        set this to ``True`` to not display :math:`T_r` text annotations
    kwargs : dict
        optional kwargs used py :ref:`gascompressibility.calc_z <calc_z>`.
    Returns
    -------
    results: dict
        dictionary of the simulation result. The structure is as follows:

        >>> results
        {
            1.05: {
                'Pr': array([0.2, 0.3, 0.4, ..., 29.9]),
                'Z': array([0.9367, 0.9030, 0.8675, ..., 3.1807]),
            },
            1.1: {
                'Pr': ...
                'Z': ...
            },
            ...
        }

        Each key: value pairs can be retrieved like this:

        >>> Pr_105 = results[1.05]['Pr']
        >>> Z_105 = results[1.05]['Z']
        >>> Pr_110 = results[1.1]['Pr']
        >>> Z_110 = results[1.1]['Z']

    fig : `Figure <https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.subplots.html>`_
        Matplotlib figure object
    ax : `Axis <https://matplotlib.org/stable/api/axis_api.html#axis-objects>`_
        Matplotlib axis object
    """
    if prmin <= 0:
        raise TypeError("Value of prmin must be greater than 0. Try prmin=0.1")

    Prs = np.linspace(prmin, prmax, round(prmax * 10 + 1))
    Prs = np.array([round(Pr, 1) for Pr in Prs])

    Trs = np.array([1.05, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0])

    results = {Tr: {
        'Pr': np.array([]),
        'Z': np.array([])
    } for Tr in Trs}

    for Tr in Trs:
        for Pr in Prs:

            if zmodel == 'kareem':
                z = calc_z(Tr=Tr, Pr=Pr, zmodel=zmodel, **kwargs)
            else:
                z = calc_z(Tr=Tr, Pr=Pr, zmodel=zmodel, newton_kwargs={'maxiter': 50}, **kwargs)

            results[Tr]['Z'] = np.append(results[Tr]['Z'], [z], axis=0)
            results[Tr]['Pr'] = np.append(results[Tr]['Pr'], [Pr], axis=0)

    label_fontsize = 12

    fig, ax = plt.subplots(figsize=figsize)
    for Tr in Trs:

        Zs = results[Tr]['Z']
        idx_min = np.where(Zs == min(Zs))[0][0]

        p = ax.plot(Prs, Zs)

        if not disable_tr_annotation:
            if Tr == 1.05:
                t = ax.text(Prs[idx_min] - 0.5, min(Zs) - 0.005, '$T_{r}$ = 1.05', color=p[0].get_color())
                t.set_bbox(dict(facecolor='white', alpha=0.9, edgecolor='white', pad=1))
                pass
            else:
                t = ax.text(Prs[idx_min] - 0.2, min(Zs) - 0.005, Tr, color=p[0].get_color())
                t.set_bbox(dict(facecolor='white', alpha=0.9, edgecolor='white', pad=1))
                pass

    ax.set_xlim(prmin, prmax)

    ax.minorticks_on()
    ax.grid(alpha=0.5)
    ax.grid(visible=True, which='minor', alpha=0.1)
    ax.spines.top.set_visible(False)
    ax.spines.right.set_visible(False)

    ax.set_ylabel('Compressibility Factor, $Z$', fontsize=label_fontsize)
    ax.set_xlabel('Pseudo-Reduced Pressure, $P_{r}$', fontsize=label_fontsize)
    ax.text(0.57, 0.08, '$T_{r}$ = Pseudo-Reduced Temperature', fontsize=11, transform=ax.transAxes,
            bbox=dict(facecolor='white'))
    ax.text(0.05, 0.9, "zmodel = '%s'" % zmodel, fontsize=11, transform=ax.transAxes,
            bbox=dict(facecolor='white'), va='center', ha='left')

    def setbold(txt):
        return ' '.join([r"$\bf{" + item + "}$" for item in txt.split(' ')])

    if title_bold is None:
        title_bold = setbold('Gas Compressibility Factor - Z')
    else:
        title_bold = setbold(title_bold)

    if title_plain is None:
        title_plain = ', computed with GasCompressiblityFactor-py '

    fig.suptitle(title_bold + title_plain, verticalalignment='top', x=0, horizontalalignment='left', fontsize=12)
    ax.annotate('', xy=(0.01, title_underline_loc), xycoords='figure fraction', xytext=(1.02, title_underline_loc),
                arrowprops=dict(arrowstyle="-", color='k'))

    fig.tight_layout()

    return results, fig, ax
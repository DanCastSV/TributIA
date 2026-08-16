/*
 * Simulador "¿qué pasaría si...?" del Centro de Análisis.
 * Recalcula tramo ISR y ahorro estimado en el cliente, sin ida y vuelta
 * al servidor: los mismos umbrales públicos que ya usa el backend en
 * core/datos_el_salvador.py (obtener_tasa_isr) y en las vistas.
 */
(function () {
    var TRAMOS = [
        { hasta: 50000, tasa: 0, nombre: 'Exento' },
        { hasta: 156000, tasa: 5, nombre: 'Tramo 5%' },
        { hasta: 300000, tasa: 10, nombre: 'Tramo 10%' },
        { hasta: Infinity, tasa: 30, nombre: 'Tramo 30%' },
    ];

    function tramoPara(salarioAnual) {
        for (var i = 0; i < TRAMOS.length; i++) {
            if (salarioAnual <= TRAMOS[i].hasta) return TRAMOS[i];
        }
        return TRAMOS[TRAMOS.length - 1];
    }

    function formatoMoneda(valor) {
        return '$' + valor.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function recalcular() {
        var salarioInput = document.getElementById('sim-salario');
        var deducibleInput = document.getElementById('sim-deducible');
        if (!salarioInput || !deducibleInput) return;

        var salarioMensual = parseFloat(salarioInput.value) || 0;
        var deducible = parseFloat(deducibleInput.value) || 0;
        var salarioAnual = salarioMensual * 12;
        var tramo = tramoPara(salarioAnual);
        var ahorro = deducible * (tramo.tasa / 100);

        document.getElementById('sim-salario-anual').textContent = formatoMoneda(salarioAnual);
        document.getElementById('sim-tramo').textContent = tramo.nombre;
        document.getElementById('sim-ahorro').textContent = formatoMoneda(ahorro);
    }

    document.addEventListener('DOMContentLoaded', function () {
        var salarioInput = document.getElementById('sim-salario');
        var deducibleInput = document.getElementById('sim-deducible');
        if (!salarioInput || !deducibleInput) return;

        salarioInput.addEventListener('input', recalcular);
        deducibleInput.addEventListener('input', recalcular);
        recalcular();
    });
})();

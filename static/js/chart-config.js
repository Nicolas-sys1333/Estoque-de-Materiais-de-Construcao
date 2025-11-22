// static/js/chart-config.js

document.addEventListener('DOMContentLoaded', function () {
    if (typeof Chart !== 'undefined') {
        // --- Configuração Global para o Tema Escuro ---

        // Define a cor da fonte padrão para todos os textos do gráfico
        Chart.defaults.color = '#666'; // Cor de texto padrão para tema claro

        // Define as cores das linhas de grade e dos eixos
        Chart.defaults.scale.grid.color = 'rgba(0, 0, 0, 0.1)';
        Chart.defaults.scale.grid.borderColor = 'rgba(0, 0, 0, 0.1)';
        
        // Define a cor do texto dos eixos (ticks)
        Chart.defaults.scale.ticks.color = '#666';

        // --- Paleta de Cores para os Dados do Gráfico ---
        // Estas cores foram escolhidas para ter um bom contraste com o fundo escuro.
        const darkThemeColors = {
            blue: 'rgba(74, 108, 140, 0.8)',   // --cor-secundaria
            blue_border: 'rgba(74, 108, 140, 1)',
            green: 'rgba(40, 167, 69, 0.8)',   // --cor-sucesso
            green_border: 'rgba(40, 167, 69, 1)',
            cyan: 'rgba(23, 162, 184, 0.8)',    // --cor-info
            cyan_border: 'rgba(23, 162, 184, 1)',
            red: 'rgba(220, 53, 69, 0.8)',     // --cor-perigo
            red_border: 'rgba(220, 53, 69, 1)',
            yellow: 'rgba(255, 193, 7, 0.8)', // --cor-aviso
            yellow_border: 'rgba(255, 193, 7, 1)',
        };

        // Você pode usar essas cores ao criar seus gráficos. Por exemplo:
        /*
        new Chart(ctx, {
            type: 'bar',
            data: {
                datasets: [{
                    label: 'Entradas',
                    backgroundColor: darkThemeColors.green,
                    borderColor: darkThemeColors.green_border,
                    // ...
                }, {
                    label: 'Saídas',
                    backgroundColor: darkThemeColors.red,
                    borderColor: darkThemeColors.red_border,
                    // ...
                }]
            }
        });
        */
    }
});

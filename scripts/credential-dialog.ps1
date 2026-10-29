function Show-IngestCredential([string]$Token) {
    if ($Token -cnotmatch '^[0-9a-f]{64}$') { throw 'Stored ingest credential format is invalid.' }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $form = New-Object Windows.Forms.Form
    $timer = New-Object Windows.Forms.Timer
    try {
        $form.Text = 'SleepIQ - private phone test setup'
        $form.ClientSize = New-Object Drawing.Size(820, 200)
        $form.StartPosition = 'CenterScreen'
        $form.FormBorderStyle = 'FixedDialog'
        $form.MaximizeBox = $false
        $form.MinimizeBox = $false
        $instructions = New-Object Windows.Forms.Label
        $instructions.Location = New-Object Drawing.Point(16, 16)
        $instructions.Size = New-Object Drawing.Size(785, 48)
        $instructions.Text = 'Type this into the Shortcut input prompt on your iPhone. It is the SleepIQ ingest credential, NOT your Cloudflare token. Do not photograph, share, or paste it into chat.'
        $label = New-Object Windows.Forms.Label
        $label.Location = New-Object Drawing.Point(16, 74)
        $label.Size = New-Object Drawing.Size(790, 30)
        $label.Font = New-Object Drawing.Font('Consolas', 13)
        $label.Text = '*' * 64
        $reveal = New-Object Windows.Forms.CheckBox
        $reveal.Location = New-Object Drawing.Point(16, 115)
        $reveal.Size = New-Object Drawing.Size(550, 28)
        $reveal.Text = 'Show credential for manual entry (window closes after 3 minutes)'
        $reveal.Add_CheckedChanged({
            $label.Text = if ($reveal.Checked) { $Token } else { '*' * 64 }
        })
        $close = New-Object Windows.Forms.Button
        $close.Location = New-Object Drawing.Point(690, 152)
        $close.Size = New-Object Drawing.Size(110, 30)
        $close.Text = 'Close'
        $close.Add_Click({ $form.Close() })
        $form.Controls.AddRange(@($instructions, $label, $reveal, $close))
        $timer.Interval = 180000
        $timer.Add_Tick({ $form.Close() })
        $timer.Start()
        $null = $form.ShowDialog()
        $label.Text = ''
    } finally {
        $timer.Stop()
        $timer.Dispose()
        $form.Dispose()
        $Token = $null
    }
}

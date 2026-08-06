<script lang="ts">
  import { t } from '$lib/i18n';
  import Icon from '$lib/components/common/Icon.svelte';
  import { agentPermissions, setAgentPermissions } from '$lib/stores/shellStore';

  function toggleFiles() {
    setAgentPermissions({ files: !$agentPermissions.files });
  }

  function toggleShell() {
    setAgentPermissions({ shell: !$agentPermissions.shell });
  }

  function toggleComputerUse() {
    setAgentPermissions({ computerUse: !$agentPermissions.computerUse });
  }

  function toggleTools() {
    setAgentPermissions({ tools: !$agentPermissions.tools });
  }

  function toggleInternet() {
    setAgentPermissions({ internet: !$agentPermissions.internet });
  }
</script>

<section aria-labelledby="settings-permissions" class="permissions-section">
  <header class="section-header">
    <h3 id="settings-permissions">{$t('permissions.title')}</h3>
    <p class="description">{$t('permissions.desc')}</p>
  </header>

  <div class="permission-list">
    <!-- Files Permission -->
    <div class="permission-item">
      <div class="info">
        <div class="icon-wrap" class:active={$agentPermissions.files}>
          <Icon name="folder" size={24} />
        </div>
        <div>
          <h4>{$t('permissions.files')}</h4>
          <p>{$t('permissions.files_desc')}</p>
        </div>
      </div>
      <button 
        type="button" 
        class="toggle-switch" 
        class:on={$agentPermissions.files} 
        onclick={toggleFiles}
        aria-pressed={$agentPermissions.files}
        title={$t('permissions.files')}
      >
        <span class="knob"></span>
      </button>
    </div>

    <!-- Shell Permission -->
    <div class="permission-item">
      <div class="info">
        <div class="icon-wrap" class:active={$agentPermissions.shell}>
          <Icon name="terminal" size={24} />
        </div>
        <div>
          <h4>{$t('permissions.shell')}</h4>
          <p>{$t('permissions.shell_desc')}</p>
        </div>
      </div>
      <button 
        type="button" 
        class="toggle-switch" 
        class:on={$agentPermissions.shell} 
        onclick={toggleShell}
        aria-pressed={$agentPermissions.shell}
        title={$t('permissions.shell')}
      >
        <span class="knob"></span>
      </button>
    </div>

    <!-- Computer Use Permission -->
    <div class="permission-item">
      <div class="info">
        <div class="icon-wrap" class:active={$agentPermissions.computerUse}>
          <Icon name="monitor" size={24} />
        </div>
        <div>
          <h4>{$t('permissions.computer_use')}</h4>
          <p>{$t('permissions.computer_use_desc')}</p>
        </div>
      </div>
      <button 
        type="button" 
        class="toggle-switch" 
        class:on={$agentPermissions.computerUse} 
        onclick={toggleComputerUse}
        aria-pressed={$agentPermissions.computerUse}
        title={$t('permissions.computer_use')}
      >
        <span class="knob"></span>
      </button>
    </div>

    <!-- Internet Permission -->
    <div class="permission-item">
      <div class="info">
        <div class="icon-wrap" class:active={$agentPermissions.internet}>
          <Icon name="globe" size={24} />
        </div>
        <div>
          <h4>{$t("permissions.internet")}</h4>
          <p>{$t("permissions.internet_desc")}</p>
        </div>
      </div>
      <button 
        type="button" 
        class="toggle-switch" 
        class:on={$agentPermissions.internet} 
        onclick={toggleInternet}
        aria-pressed={$agentPermissions.internet}
        title={$t("permissions.internet")}
      >
        <span class="knob"></span>
      </button>
    </div>

    <!-- External Tools Permission -->
    <div class="permission-item">
      <div class="info">
        <div class="icon-wrap" class:active={$agentPermissions.tools}>
          <Icon name="plug" size={24} />
        </div>
        <div>
          <h4>{$t('permissions.tools')}</h4>
          <p>{$t('permissions.tools_desc')}</p>
        </div>
      </div>
      <button 
        type="button" 
        class="toggle-switch" 
        class:on={$agentPermissions.tools} 
        onclick={toggleTools}
        aria-pressed={$agentPermissions.tools}
        title={$t('permissions.tools')}
      >
        <span class="knob"></span>
      </button>
    </div>
  </div>
</section>

<style>
  .permissions-section {
    padding: var(--lc-space-2) 0;
  }

  .section-header {
    margin-bottom: var(--lc-space-4);
  }

  .description {
    color: var(--lc-faint);
    font-size: 0.9rem;
    margin-top: 4px;
  }

  .permission-list {
    display: flex;
    flex-direction: column;
    gap: var(--lc-space-3);
  }

  .permission-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--lc-space-3);
    border: var(--border-thin);
    border-radius: var(--radius-md);
    background: var(--lc-surface-elevated);
    transition: border-color 0.2s ease, background 0.2s ease;
  }

  .permission-item:hover {
    border-color: var(--lc-primary-alpha);
    background: var(--lc-panel-solid);
  }

  .info {
    display: flex;
    align-items: center;
    gap: var(--lc-space-3);
  }

  .icon-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    border-radius: var(--radius-sm);
    background: var(--lc-border);
    color: var(--lc-muted);
    transition: all 0.2s ease;
  }

  .icon-wrap.active {
    background: var(--lc-primary-alpha);
    color: var(--lc-primary);
  }

  h4 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--lc-text);
  }

  p {
    margin: 2px 0 0 0;
    font-size: 0.85rem;
    color: var(--lc-muted);
  }

  /* Toggle Switch */
  .toggle-switch {
    position: relative;
    width: 44px;
    height: 24px;
    border-radius: 12px;
    background: var(--lc-border);
    border: none;
    cursor: pointer;
    transition: background 0.3s ease;
    padding: 0;
    display: flex;
    align-items: center;
  }

  .toggle-switch.on {
    background: var(--lc-primary);
  }

  .knob {
    position: absolute;
    left: 2px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
    transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
  }

  .toggle-switch.on .knob {
    transform: translateX(20px);
  }

  .toggle-switch:focus-visible {
    outline: 2px solid var(--lc-primary);
    outline-offset: 2px;
  }
</style>

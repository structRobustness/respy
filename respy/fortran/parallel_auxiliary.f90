!******************************************************************************
!******************************************************************************
MODULE parallel_auxiliary

    !/* external modules    */

    USE parallel_constants

    USE resfort_library

    USE mpi

    !/* setup   */

    IMPLICIT NONE

    PUBLIC

CONTAINS
!******************************************************************************
!******************************************************************************
SUBROUTINE fort_solve_parallel(periods_payoffs_systematic, states_number_period, mapping_state_idx, periods_emax, states_all, coeffs_a, coeffs_b, coeffs_edu, coeffs_home, shocks_cholesky)

    !/* external objects        */

    INTEGER(our_int), ALLOCATABLE, INTENT(INOUT)    :: mapping_state_idx(:, :, :, :, :)
    INTEGER(our_int), ALLOCATABLE, INTENT(INOUT)    :: states_number_period(:)
    INTEGER(our_int), ALLOCATABLE, INTENT(INOUT)    :: states_all(:, :, :)

    REAL(our_dble), ALLOCATABLE, INTENT(INOUT)      :: periods_payoffs_systematic(:, :, :)
    REAL(our_dble), ALLOCATABLE, INTENT(INOUT)      :: periods_emax(:, :)

    REAL(our_dble), INTENT(IN)                      :: shocks_cholesky(4, 4)
    REAL(our_dble), INTENT(IN)                      :: coeffs_home(1)
    REAL(our_dble), INTENT(IN)                      :: coeffs_edu(3)
    REAL(our_dble), INTENT(IN)                      :: coeffs_a(6)
    REAL(our_dble), INTENT(IN)                      :: coeffs_b(6)

    !/* internal objects        */

    INTEGER(our_int), ALLOCATABLE                   :: states_all_tmp(:, :, :)

    INTEGER(our_int)                                :: num_states
    INTEGER(our_int)                                :: period
    INTEGER(our_int)            :: status

    REAL(our_dble), ALLOCATABLE :: temporary_subset(:)

!------------------------------------------------------------------------------
! Algorithm
!------------------------------------------------------------------------------

    ! If agents are not myopic, then we start a number of slaves and request to help in the calculation of the EMAX.
    IF (.NOT. is_myopic) THEN
        CALL MPI_COMM_SPAWN(TRIM(exec_dir) // '/resfort_parallel_slave', MPI_ARGV_NULL, (num_procs - 1), MPI_INFO_NULL, 0, MPI_COMM_WORLD, SLAVECOMM, MPI_ERRCODES_IGNORE, ierr)
        CALL MPI_Bcast(2, 1, MPI_INT, MPI_ROOT, SLAVECOMM, ierr)
    END IF
    
    ! While we are waiting for the slaves to work on the EMAX calculation, the master can get some work done.
    ALLOCATE(mapping_state_idx(num_periods, num_periods, num_periods, min_idx, 2))
    ALLOCATE(states_all_tmp(num_periods, 100000, 4))
    ALLOCATE(states_number_period(num_periods))

    IF(is_myopic) CALL logging_solution(1)

    CALL fort_create_state_space(states_all_tmp, states_number_period, mapping_state_idx)

    IF(is_myopic) CALL logging_solution(-1)

    ALLOCATE(periods_emax(num_periods, max_states_period))

    ! Calculate the systematic payoffs
    ALLOCATE(states_all(num_periods, max_states_period, 4))
    states_all = states_all_tmp(:, :max_states_period, :)
    DEALLOCATE(states_all_tmp)

    ALLOCATE(periods_payoffs_systematic(num_periods, max_states_period, 4))

    IF(is_myopic) CALL logging_solution(2)

    CALL fort_calculate_payoffs_systematic(periods_payoffs_systematic, states_number_period, states_all, coeffs_a, coeffs_b, coeffs_edu, coeffs_home)

    IF(is_myopic) CALL logging_solution(-1)

    periods_emax = MISSING_FLOAT


    ! The leading slave is kind enough to let the parent process know about the  intermediate outcomes.
    IF (is_myopic) THEN

        CALL logging_solution(3)
   
        ! All other objects remain set to MISSING_FLOAT. This align the treatment for the two special cases: (1) is_myopic and (2) is_interpolated.
        DO period = 1,  num_periods
            periods_emax(period, :states_number_period(period)) = zero_dble
        END DO
     
        CALL logging_solution(-2)

    ELSE

        DO period = (num_periods - 1), 0, -1

            num_states = states_number_period(period + 1)

            ALLOCATE(temporary_subset(num_states))
            CALL MPI_RECV(temporary_subset, num_states, MPI_DOUBLE, MPI_ANY_SOURCE, MPI_ANY_TAG, SLAVECOMM, status, ierr)

            periods_emax(period + 1, :num_states) = temporary_subset

            DEALLOCATE(temporary_subset)
        END DO

        CALL logging_solution(-1)

        ! Shut down orderly
        CALL MPI_Bcast(1, 1, MPI_INT, MPI_ROOT, SLAVECOMM, ierr)
        CALL MPI_FINALIZE (ierr)

    END IF


END SUBROUTINE
!******************************************************************************
!******************************************************************************
END MODULE